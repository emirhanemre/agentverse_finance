"""The five-agent chain: verifier -> ingest -> risk analyst -> hedge pricer -> monitor/proposer.

Each agent is a Google ADK LlmAgent that calls our tools. After each agent the runner
calls any required tool the model skipped, so the deterministic pipeline always
completes. If Gemini errors, times out or the spend guard trips, narration falls back
to a template with a TEMPLATE badge."""
import asyncio
import functools
import inspect
import json
import os
import time
import uuid

from . import audit, grounding
from .config import MODEL_FAST, MODEL_REASONING, REPO, SPEND_CAP_USD, offline
from .tools import Run, identity, make_tools

STEPS = [
    ("verifier", "Verifying the business", MODEL_FAST,
     "You verify a pub against public registers. First call find_postcode with pub_name '{pub_name}'; use the postcode "
     "it returns (or '{postcode}' if that is set). Call find_premises and find_operator with that pub_name and "
     "postcode. If find_operator returns a company_number, call companies_house_profile, "
     "companies_house_officer_match and register_checks with it. Call locate_postcode with that postcode. Then write two "
     "sentences: what the hygiene register and Companies House say about this pub, and any red flags. If no company "
     "was matched, say so plainly. Quote only numbers that appear in tool results."),
    ("ingest", "Loading demo books from our integrations", MODEL_FAST,
     "You load the demo books. Call every tool once. Then write one sentence on what was loaded. Say plainly that the "
     "takings, card payments and bank feed are demo books from our test integrations, not this pub's own figures, "
     "and that the weather and match dates are real. Quote only numbers that appear in tool results."),
    ("risk", "Finding what weather costs", MODEL_FAST,
     "You are the risk analyst. Call fit_takings_model and weekend_rain_exposure. Then write two sentences on the "
     "rain risk and how well the model fits held-out months. Quote only numbers from tool results; never compute."),
    ("pricer", "Pricing protection for the weekend", MODEL_FAST,
     "You price weekend rain protection. Call weekend_forecast, check_real_weather_markets, price_rain_contracts, "
     "project_payroll with scenario 'dry' and with scenario 'wet', then size_hedges. Write two sentences. If "
     "size_hedges finds nothing worth buying, say so and recommend nothing. Quote only numbers from tool results."),
    ("monitor", "Checking limits and queueing for approval", MODEL_FAST,
     "Call check_limits, then queue_for_approval, then schedule_monitor, then price_match_offer. Write one sentence "
     "on what now waits for the owner (nothing executes without a human), then one sentence on the match-day offer "
     "price_match_offer priced: its worst case and the fixed cost of covering it. Quote only numbers from tool results."),
]

PRICE_PER_M = {MODEL_FAST: (0.75, 3.75), MODEL_REASONING: (2.0, 10.0)}
SPEND_FILE = REPO / "services" / "agents" / ".spend.json"


def spent_usd() -> float:
    try:
        return json.loads(SPEND_FILE.read_text())["usd"]
    except Exception:
        return 0.0


def add_spend(model, tin, tout):
    pin, pout = PRICE_PER_M.get(model, (2.0, 10.0))
    usd = spent_usd() + (tin * pin + tout * pout) / 1e6
    SPEND_FILE.write_text(json.dumps({"usd": round(usd, 4)}))


def live_models_allowed() -> bool:
    if offline() or not os.environ.get("GOOGLE_API_KEY"):
        return False
    return spent_usd() < SPEND_CAP_USD or os.environ.get("PUBHEDGE_FORCE_LIVE") == "1"


def _model_facing(fn):
    """What the model sees from a tool: the full record minus bulky arrays."""
    @functools.wraps(fn)
    def w(**kw):
        res = fn(**kw)
        return {k: v for k, v in res.items() if k not in ("timeline", "inputs")}
    w.__signature__ = inspect.signature(fn)
    return w


async def _run_agent(run: Run, name, model, instruction, fns, context: str) -> tuple:
    from google.adk.agents import LlmAgent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    cfg = types.GenerateContentConfig(temperature=0.1, thinking_config=types.ThinkingConfig(thinking_level="low"))
    agent = LlmAgent(name=name, model=model, instruction=instruction, tools=[_model_facing(f) for f in fns],
                     generate_content_config=cfg)
    svc = InMemorySessionService()
    runner = Runner(app_name="pubhedge", agent=agent, session_service=svc)
    s = await svc.create_session(app_name="pubhedge", user_id="owner-demo")
    msg = types.Content(role="user", parts=[types.Part(text=context)])
    text, tin, tout = "", 0, 0
    async for ev in runner.run_async(user_id="owner-demo", session_id=s.id, new_message=msg):
        if ev.usage_metadata:
            tin += ev.usage_metadata.prompt_token_count or 0
            tout += (ev.usage_metadata.candidates_token_count or 0) + (ev.usage_metadata.thoughts_token_count or 0)
        if ev.is_final_response() and ev.content and ev.content.parts:
            text = "".join(p.text or "" for p in ev.content.parts if not getattr(p, "thought", False))
    return text.strip(), tin, tout


def template(step: str, outs: list) -> str:
    s = [o.get("summary", "") for o in outs if o.get("summary")]
    return "; ".join(s) + "." if s else "Step complete."


async def _rationale_call(model: str, facts: dict) -> tuple:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    prompt = ("You are a cautious risk officer writing to a pub owner. Using ONLY these tool outputs, write 3 short "
              "bullet points (plain text, start each with '- ') explaining the proposed hedge or why nothing is proposed, "
              "including what happens if it stays dry and the hedge costs money. Every number you write must appear in "
              "the facts. UK English, no hype.\nFACTS:\n" + json.dumps(facts, default=str))
    resp = await client.aio.models.generate_content(
        model=model, contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2, thinking_config=types.ThinkingConfig(thinking_level="low")))
    u = resp.usage_metadata
    return (resp.text or "").strip(), (u.prompt_token_count or 0), (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)


ARGON_TIMEOUT_S, FLASH_TIMEOUT_S = 60, 45


def _rationale_facts(tools) -> dict:
    sized = tools["pricer"][4]()
    return {"sizing": {k: v for k, v in sized.items() if k not in ("receipt_id", "timeline", "inputs")},
            "wet": {k: v for k, v in tools["pricer"][3](scenario="wet").items() if k != "timeline"},
            "dry": {k: v for k, v in tools["pricer"][3](scenario="dry").items() if k != "timeline"},
            "exposure": tools["risk"][1](), "contracts": tools["pricer"][2]()["contracts"]}


async def _timed(model: str, facts: dict, timeout: float) -> tuple:
    return await asyncio.wait_for(_rationale_call(model, facts), timeout=timeout)


def _late_argon(run_id: str, task: "asyncio.Task") -> None:
    """Argon came back after the run had moved on: keep its answer (and its cost) on the record."""
    if task.cancelled() or task.exception():
        return
    text, tin, tout = task.result()
    add_spend(MODEL_REASONING, tin, tout)
    audit.append(run_id, "rationale", "narration_late", {"model": MODEL_REASONING},
                 {"text": text, "note": "arrived after the run used Flash"}, "MODEL", MODEL_REASONING, 0, tin, tout)


async def run_chain(mode: str, emit, limits: dict, run_id: str = None, use_models: bool = True,
                    pub: dict = None) -> dict:
    run_id = run_id or "run_" + uuid.uuid4().hex[:10]
    run = Run(run_id, mode, emit, limits, pub or identity())
    tools = make_tools(run)
    t0 = time.time()
    live = use_models and live_models_allowed()
    audit.db().execute("INSERT INTO runs (run_id, mode, started, status) VALUES (?,?,?,?)",
                       (run_id, mode, t0, "running"))
    audit.db().commit()
    emit({"type": "run", "run_id": run_id, "mode": mode, "live_models": live, "pub": run.pub})
    narr = {}
    prev = f"Pub: {run.pub['entered_name']}, {run.pub['entered_postcode']}. Mode: {mode}."
    for step, label, model, instruction in STEPS:
        run.step, run.model = step, (model if live else "template")
        st = time.time()
        emit({"type": "step_start", "step": step, "label": label, "model": run.model})
        text, badge, tin, tout = "", "MODEL", 0, 0
        n_before = len(run.outputs)
        if live:
            try:
                text, tin, tout = await asyncio.wait_for(
                    _run_agent(run, step, model, instruction.format(pub_name=run.pub['entered_name'],
                                                                 postcode=run.pub['entered_postcode']), tools[step], prev), timeout=45)
                add_spend(model, tin, tout)
            except Exception as exc:
                text, badge = "", f"TEMPLATE · {type(exc).__name__}"
        run.model = model if live else "template"
        # required tools: anything the model skipped runs deterministically
        for fn in tools[step]:
            params = inspect.signature(fn).parameters
            kw = {}
            if "company_number" in params:
                if not run.pub.get("company_number"):
                    continue  # no company matched: nothing to look up
                kw["company_number"] = run.pub["company_number"]
            if "pub_name" in params:
                kw["pub_name"] = run.pub["entered_name"]
            if "postcode" in params:
                kw["postcode"] = run.pub["entered_postcode"]
            if "scenario" in params:
                for sc in ("dry", "wet"):
                    fn(scenario=sc)
                continue
            fn(**kw)
        step_outs = run.outputs[n_before:]
        if not text:
            text, badge = template(step, step_outs), (badge if badge != "MODEL" else "TEMPLATE")
        g = grounding.check(text, run.outputs)
        if not g["ok"]:
            badge += " · GROUNDING FLAG"
        final = g["text"] or template(step, step_outs)
        row = audit.append(run_id, step, "narration", {"model": run.model}, {"text": final, "grounding": g, "badge": badge},
                           badge, run.model, int((time.time() - st) * 1000), tin, tout)
        narr[step] = {"text": final, "badge": badge, "grounding": g, "receipt_id": row["receipt_id"]}
        emit({"type": "step_end", "step": step, "label": label, "model": run.model, "narration": final,
              "narration_badge": badge, "grounding_ok": g["ok"], "receipt_id": row["receipt_id"],
              "ms": int((time.time() - st) * 1000), "tokens": tin + tout})
        prev = f"Previous step ({step}) found: {final}"
        if live and step == "pricer":
            # Everything the rationale needs exists now. Argon (slow, better) and Flash (fast) start writing it
            # while the monitor step runs; whichever the end of the run finds ready is used.
            facts = _rationale_facts(tools)
            argon_task = asyncio.create_task(_timed(MODEL_REASONING, facts, ARGON_TIMEOUT_S))
            flash_task = asyncio.create_task(_timed(MODEL_FAST, facts, FLASH_TIMEOUT_S))
    # the hedge rationale: Argon if it is back, otherwise Flash (flagged), otherwise the template
    run.step, run.model = "rationale", (MODEL_REASONING if live else "template")
    if not live:
        facts = _rationale_facts(tools)
    st = time.time()
    text, badge, tin, tout, note = "", "MODEL", 0, 0, None
    if live:
        def ok(t):
            return t.done() and not t.cancelled() and t.exception() is None and t.result()[0]
        if not ok(argon_task) and not argon_task.done():
            # Argon still thinking: take Flash as soon as it lands, unless Argon beats it there.
            await asyncio.wait({argon_task, flash_task}, return_when=asyncio.FIRST_COMPLETED)
            if not ok(argon_task) and not flash_task.done():
                await asyncio.wait({flash_task})
            if not ok(flash_task) and not argon_task.done():
                await asyncio.wait({argon_task})  # Flash failed: Argon is the only model answer left
        if ok(argon_task):
            text, tin, tout = argon_task.result()
            add_spend(MODEL_REASONING, tin, tout)
            flash_task.cancel()
        elif ok(flash_task):
            text, tin, tout = flash_task.result()
            add_spend(MODEL_FAST, tin, tout)
            run.model = MODEL_FAST
            if argon_task.done():
                note = "Flash used: Argon failed"
            else:
                note = "Flash used, Argon not back yet"
                argon_task.add_done_callback(lambda t: _late_argon(run_id, t))
        else:
            exc = (argon_task.exception() if argon_task.done() and not argon_task.cancelled() else None)
            badge = f"TEMPLATE · {type(exc).__name__ if exc else 'NoModelReply'}"
            argon_task.cancel()
    if not text:
        text = rationale_template(facts)
        badge = badge if badge != "MODEL" else "TEMPLATE"
        run.model = "template"
    g = grounding.check(text, run.outputs)
    if not g["ok"]:
        badge += " · GROUNDING FLAG"
    row = audit.append(run_id, "rationale", "narration", {"model": run.model}, {"text": g["text"], "grounding": g, "note": note},
                       badge, run.model, int((time.time() - st) * 1000), tin, tout)
    narr["rationale"] = {"text": g["text"], "badge": badge, "grounding": g, "receipt_id": row["receipt_id"],
                         "model": run.model, "note": note}
    emit({"type": "rationale", "model": run.model, "text": g["text"], "badge": badge, "grounding_ok": g["ok"],
          "receipt_id": row["receipt_id"], "ms": int((time.time() - st) * 1000), "note": note})
    wall = int((time.time() - t0) * 1000)
    summary = {"run_id": run_id, "mode": mode, "wall_ms": wall, "narration": narr, "live_models": live, "pub": run.pub}
    audit.db().execute("UPDATE runs SET finished=?, wall_ms=?, status=?, summary=? WHERE run_id=?",
                       (time.time(), wall, "done", json.dumps(summary), run_id))
    audit.db().commit()
    emit({"type": "done", "run_id": run_id, "wall_ms": wall})
    return summary


def rationale_template(f: dict) -> str:
    s, wet, dry = f["sizing"], f["wet"], f["dry"]
    if not s["positions"]:
        return (f"- Nothing is worth buying at today's prices, so nothing is proposed.\n"
                f"- If the weekend is wet, payroll on {wet['payroll_date']} is short £{wet['shortfall_gbp']:,.2f}.")
    p, o = s["positions"][0], s.get("outcomes", {})

    def payroll_line(headroom):
        return f"clears with £{headroom:,.2f} to spare" if headroom >= 0 else f"is short £{-headroom:,.2f}"
    wet_h = o.get("wet_with_hedge_headroom_gbp", -wet["shortfall_gbp"])
    dry_h = o.get("dry_with_hedge_headroom_gbp", -dry["shortfall_gbp"])
    return (f"- A wet afternoon costs about £{f['exposure']['loss_wet_day_gbp']:,.2f} in takings.\n"
            f"- The proposed position costs £{s['total_cost_gbp']:.2f} and pays £{p['payout_if_event_gbp']:,.2f} if it rains, "
            f"so payroll on {wet['payroll_date']} {payroll_line(wet_h)}.\n"
            f"- If it stays dry the £{s['total_cost_gbp']:.2f} is lost, and payroll {payroll_line(dry_h)}.")
