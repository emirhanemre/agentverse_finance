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
from .tools import PUB, Run, make_tools

STEPS = [
    ("verifier", "Verifying the business", MODEL_FAST,
     f"You verify a pub against public registers. Call companies_house_profile and companies_house_officer_match "
     f"with company_number '{PUB['company_number']}', and locate_postcode with '{PUB['postcode']}'. Then write one "
     "sentence on whether the business checks out. Quote only numbers that appear in tool results."),
    ("ingest", "Reading takings, bank feed and history", MODEL_FAST,
     "You load the pub's data. Call every tool once. Then write one sentence on what was loaded, saying which data "
     "is synthetic. Quote only numbers that appear in tool results."),
    ("risk", "Finding what weather costs", MODEL_FAST,
     "You are the risk analyst. Call fit_takings_model and weekend_rain_exposure. Then write two sentences on the "
     "rain risk and how well the model fits held-out months. Quote only numbers from tool results; never compute."),
    ("pricer", "Pricing protection for the weekend", MODEL_FAST,
     "You price weekend rain protection. Call weekend_forecast, check_real_weather_markets, price_rain_contracts, "
     "project_payroll with scenario 'dry' and with scenario 'wet', then size_hedges. Write two sentences. If "
     "size_hedges finds nothing worth buying, say so and recommend nothing. Quote only numbers from tool results."),
    ("monitor", "Checking limits and queueing for approval", MODEL_FAST,
     "Call check_limits, then queue_for_approval, then schedule_monitor. Write one sentence on what now waits for "
     "the owner. Nothing executes without a human. Quote only numbers from tool results."),
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


async def _argon_rationale(run: Run, facts: dict) -> tuple:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    prompt = ("You are a cautious risk officer writing to a pub owner. Using ONLY these tool outputs, write 3 short "
              "bullet points (plain text, start each with '- ') explaining the proposed hedge or why nothing is proposed, "
              "including what happens if it stays dry and the hedge costs money. Every number you write must appear in "
              "the facts. UK English, no hype.\nFACTS:\n" + json.dumps(facts, default=str))
    resp = await client.aio.models.generate_content(
        model=MODEL_REASONING, contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2, thinking_config=types.ThinkingConfig(thinking_level="low")))
    u = resp.usage_metadata
    return (resp.text or "").strip(), (u.prompt_token_count or 0), (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)


async def run_chain(mode: str, emit, limits: dict, run_id: str = None) -> dict:
    run_id = run_id or "run_" + uuid.uuid4().hex[:10]
    run = Run(run_id, mode, emit, limits)
    tools = make_tools(run)
    t0 = time.time()
    live = live_models_allowed()
    audit.db().execute("INSERT INTO runs (run_id, mode, started, status) VALUES (?,?,?,?)",
                       (run_id, mode, t0, "running"))
    audit.db().commit()
    emit({"type": "run", "run_id": run_id, "mode": mode, "live_models": live})
    narr = {}
    prev = f"Pub: {PUB['trading_name']}, {PUB['address']}. Mode: {mode}."
    for step, label, model, instruction in STEPS:
        run.step, run.model = step, (model if live else "template")
        st = time.time()
        emit({"type": "step_start", "step": step, "label": label, "model": run.model})
        text, badge, tin, tout = "", "MODEL", 0, 0
        n_before = len(run.outputs)
        if live:
            try:
                text, tin, tout = await asyncio.wait_for(
                    _run_agent(run, step, model, instruction, tools[step], prev), timeout=45)
                add_spend(model, tin, tout)
            except Exception as exc:
                text, badge = "", f"TEMPLATE · {type(exc).__name__}"
        run.model = model if live else "template"
        # required tools: anything the model skipped runs deterministically
        for fn in tools[step]:
            params = inspect.signature(fn).parameters
            kw = {}
            if "company_number" in params:
                kw["company_number"] = PUB["company_number"]
            if "postcode" in params:
                kw["postcode"] = PUB["postcode"]
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
    # one reasoning-model call for the hedge rationale
    run.step, run.model = "rationale", (MODEL_REASONING if live else "template")
    sized = tools["pricer"][4]()
    facts = {"sizing": {k: v for k, v in sized.items() if k != "receipt_id"},
             "wet": {k: v for k, v in tools["pricer"][3](scenario="wet").items() if k != "timeline"},
             "dry": {k: v for k, v in tools["pricer"][3](scenario="dry").items() if k != "timeline"},
             "exposure": tools["risk"][1](), "contracts": tools["pricer"][2]()["contracts"]}
    st = time.time()
    text, badge, tin, tout = "", "MODEL", 0, 0
    if live:
        try:
            text, tin, tout = await asyncio.wait_for(_argon_rationale(run, facts), timeout=60)
            add_spend(MODEL_REASONING, tin, tout)
        except Exception as exc:
            badge = f"TEMPLATE · {type(exc).__name__}"
    if not text:
        text = rationale_template(facts)
        badge = badge if badge != "MODEL" else "TEMPLATE"
        run.model = "template"
    g = grounding.check(text, run.outputs)
    if not g["ok"]:
        badge += " · GROUNDING FLAG"
    row = audit.append(run_id, "rationale", "narration", {"model": run.model}, {"text": g["text"], "grounding": g},
                       badge, run.model, int((time.time() - st) * 1000), tin, tout)
    narr["rationale"] = {"text": g["text"], "badge": badge, "grounding": g, "receipt_id": row["receipt_id"],
                         "model": run.model}
    emit({"type": "rationale", "model": run.model, "text": g["text"], "badge": badge, "grounding_ok": g["ok"],
          "receipt_id": row["receipt_id"], "ms": int((time.time() - st) * 1000)})
    wall = int((time.time() - t0) * 1000)
    summary = {"run_id": run_id, "mode": mode, "wall_ms": wall, "narration": narr, "live_models": live}
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
    p = s["positions"][0]
    return (f"- A wet afternoon costs about £{f['exposure']['loss_wet_day_gbp']:,.2f} in takings.\n"
            f"- The proposed position costs £{s['total_cost_gbp']:.2f} and pays £{p['payout_if_event_gbp']:,.2f} if it rains.\n"
            f"- If it stays dry the £{s['total_cost_gbp']:.2f} is lost, and payroll on {dry['payroll_date']} is still "
            f"short £{dry['shortfall_gbp']:,.2f}.")
