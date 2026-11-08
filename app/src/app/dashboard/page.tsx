"use client";

import { useState } from "react";
import { API, useAppState } from "../../lib/api";
import { NAV, Sidebar, TopBar, type NavId } from "../../components/dashboard/Shell";
import { TodayView } from "../../components/dashboard/Overview";
import { ActivityPage, BacktestPage, ProtectionsPage, RisksPage, SettingsPage, SourcesPage } from "../../components/dashboard/Pages";
import { ModelChip } from "../../components/AgentRun";
import { Spinner } from "../../components/ui";

export default function DashboardPage() {
  const { state: s, error, refresh: load } = useAppState();
  const [nav, setNav] = useState<NavId>("overview");
  const [tick, setTick] = useState(0);
  const refresh = () => {
    load();
    setTick((t) => t + 1);
  };
  const title = NAV.find((n) => n.id === nav)?.label ?? "";

  if (!s)
    return (
      <div className="flex h-screen items-center justify-center text-[13px] text-fg-2">
        {error ? <span className="text-negative">Can’t reach the Pub Hedge API at {API}. Is it running?</span> : <Spinner className="text-accent" />}
      </div>
    );

  const district = s.tools.locate_postcode?.[0]?.district;
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar nav={nav} onNav={setNav} pubName={s.pub.trading_name} place={`${s.pub.postcode}${district ? ` · ${district}` : ""}`} owner={s.pub.owner} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          title={title}
          right={
            s.run && (
              <span className="flex items-center gap-2 font-mono text-[11.5px] text-fg-3">
                {s.scenario.name} · {s.run.mode} · {s.run.run_id}
                <ModelChip model={s.run.summary?.narration?.rationale?.model ?? (s.run.summary?.live_models ? "model" : "template")} />
              </span>
            )
          }
        />
        <main className="min-h-0 flex-1 overflow-y-auto p-4">
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
