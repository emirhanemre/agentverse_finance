"use client";

import { useEffect, useState } from "react";
import { API, useAppState } from "../../lib/api";
import { MobileNav, NAV, Sidebar, TopBar, ViewSwitch, type NavId, type View } from "../../components/dashboard/Shell";
import { SimpleView } from "../../components/dashboard/Simple";
import { TodayView } from "../../components/dashboard/Overview";
import { ActivityPage, BacktestPage, ProtectionsPage, RisksPage, SettingsPage, SourcesPage } from "../../components/dashboard/Pages";
import { DemoBooksChip, ModelChip } from "../../components/AgentRun";
import { Logo, Spinner } from "../../components/ui";

const VIEW_KEY = "pubhedge.view";

export default function DashboardPage() {
  const { state: s, error, refresh: load } = useAppState();
  const [nav, setNav] = useState<NavId>("overview");
  const [tick, setTick] = useState(0);
  const [view, setViewState] = useState<View>("simple");
  useEffect(() => {
    // ?view=advanced wins; otherwise the owner's last choice; Simple by default
    const q = new URLSearchParams(window.location.search).get("view");
    let saved: string | null = null;
    try {
      saved = localStorage.getItem(VIEW_KEY);
    } catch {}
    if (q === "advanced" || q === "simple") setViewState(q);
    else if (saved === "advanced") setViewState("advanced");
  }, []);
  const setView = (v: View) => {
    setViewState(v);
    try {
      localStorage.setItem(VIEW_KEY, v);
    } catch {}
    const url = new URL(window.location.href);
    url.searchParams.set("view", v);
    window.history.replaceState(null, "", url); // the view lives in the URL too, so a reload or a shared link keeps it
  };
  const refresh = () => {
    load();
    setTick((t) => t + 1);
  };
  const title = NAV.find((n) => n.id === nav)?.label ?? "";

  if (!s)
    return (
      <div className="flex h-screen items-center justify-center text-sm text-fg-2">
        {error ? <span className="text-negative">Can’t reach the Pub Hedge API at {API}. Is it running?</span> : <Spinner className="text-accent" />}
      </div>
    );

  const district = s.tools.locate_postcode?.[0]?.district;
  if (view === "simple")
    return (
      <div className="flex h-screen flex-col overflow-hidden">
        <TopBar
          title={
            <span className="flex items-center gap-3 whitespace-nowrap">
              <Logo />
              <span className="hidden h-4 w-px bg-line-strong sm:block" aria-hidden />
              <span className="hidden font-sans text-sm font-normal text-fg-2 sm:inline">{s.pub.trading_name}</span>
              <span className="hidden sm:inline">
                <DemoBooksChip />
              </span>
            </span>
          }
          right={<ViewSwitch view={view} onChange={setView} />}
        />
        <main className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6">
          <SimpleView s={s} refresh={refresh} />
        </main>
      </div>
    );
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar nav={nav} onNav={setNav} pubName={s.pub.trading_name} place={`${s.pub.postcode}${district ? ` · ${district}` : ""}`} owner={s.pub.owner} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          title={title}
          right={
            <>
              {s.run && (
                <span className="hidden items-center gap-3 whitespace-nowrap text-xs text-fg-3 xl:flex">
                  <span>{s.scenario.name}</span>
                  <span className="h-3 w-px bg-line-strong" aria-hidden />
                  <span>{s.run.mode}</span>
                  <span className="h-3 w-px bg-line-strong" aria-hidden />
                  <span className="font-mono">{s.run.run_id}</span>
                  <ModelChip model={s.run.summary?.narration?.rationale?.model ?? (s.run.summary?.live_models ? "model" : "template")} />
                </span>
              )}
              <ViewSwitch view={view} onChange={setView} />
            </>
          }
        />
        <MobileNav nav={nav} onNav={setNav} />
        <main className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
          {nav === "overview" && <TodayView s={s} refresh={refresh} tick={tick} />}
          {nav === "protections" && <ProtectionsPage s={s} refresh={refresh} />}
          {nav === "risks" && <RisksPage s={s} />}
          {nav === "backtest" && <BacktestPage s={s} />}
          {nav === "activity" && <ActivityPage tick={tick} />}
          {nav === "sources" && <SourcesPage s={s} />}
          {nav === "settings" && <SettingsPage s={s} refresh={refresh} />}
        </main>
      </div>
    </div>
  );
}
