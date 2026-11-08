"use client";

import { useEffect, useState } from "react";
import { HEDGES, PUB, loadSetup, type SetupState } from "./lib/data";
import type { Timeline } from "./lib/dashboard-data";
import { NAV, Sidebar, TopBar, type NavId } from "./components/dashboard/Shell";
import { RainView, TodayView, YearView, type Approval } from "./components/dashboard/Overview";
import { ActivityPage, ProtectionsPage, RisksPage, SettingsPage, SourcesPage } from "./components/dashboard/Pages";

export default function DashboardPage() {
  const [setup, setSetup] = useState<SetupState>({ pubName: PUB.name, owner: PUB.owner, hedges: HEDGES.map((h) => h.id) });
  const [nav, setNav] = useState<NavId>("overview");
  const [timeline, setTimeline] = useState<Timeline>("today");
  const [approval, setApproval] = useState<Approval>("pending");

  useEffect(() => setSetup(loadSetup()), []);

  const hedges = HEDGES.filter((h) => setup.hedges.includes(h.id));
  const title = NAV.find((n) => n.id === nav)?.label ?? "";

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar nav={nav} onNav={setNav} pubName={setup.pubName} owner={setup.owner} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          title={title}
          timeline={timeline}
          onTimeline={(t) => {
            setTimeline(t);
            setNav("overview");
          }}
          alert={approval === "pending" && timeline === "today"}
        />
        <main className="min-h-0 flex-1 overflow-y-auto p-4">
          {nav === "overview" && timeline === "today" && <TodayView hedges={hedges} approval={approval} onApproval={setApproval} />}
          {nav === "overview" && timeline === "rain" && <RainView hedges={hedges} />}
          {nav === "overview" && timeline === "year" && <YearView />}
          {nav === "protections" && <ProtectionsPage hedges={hedges} timeline={timeline} />}
          {nav === "risks" && <RisksPage />}
          {nav === "activity" && <ActivityPage timeline={timeline} />}
          {nav === "sources" && <SourcesPage />}
          {nav === "settings" && <SettingsPage />}
        </main>
      </div>
    </div>
  );
}
