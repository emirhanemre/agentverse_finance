"use client";
import { useState } from "react";
import {
  NAV,
  Sidebar,
  TopBar,
  type NavId,
  type Timeline,
} from "../../components/dashboard/Shell";
import {
  HistoryView,
  ScenarioView,
  TodayView,
} from "../../components/dashboard/Overview";
import {
  ActivityPage,
  ProtectionsPage,
  RisksPage,
  SettingsPage,
  SourcesPage,
} from "../../components/dashboard/Pages";
import { useApplication } from "../../lib/api";
import { ErrorNotice } from "../../components/onboarding/Onboarding";
import { Empty } from "../../components/onboarding/PlanSteps";
import { Panel } from "../../components/ui";

export default function DashboardPage() {
  const { state, error, refresh } = useApplication();
  const [nav, setNav] = useState<NavId>("overview"),
    [timeline, setTimeline] = useState<Timeline>("today");
  const title = NAV.find((n) => n.id === nav)?.label || "Overview";
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        nav={nav}
        onNav={setNav}
        pubName={state?.profile?.pubName || "Your business"}
        owner={state?.profile?.owner || "Local operator"}
        postcode={state?.profile?.postcode || "Not configured"}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          title={title}
          timeline={timeline}
          onTimeline={(t) => {
            setTimeline(t);
            setNav("overview");
          }}
          alert={
            !!state?.summary.pending_approvals ||
            !!state?.notifications.some((n) => !n.read_at)
          }
          onNotifications={() => setNav("activity")}
        />
        <main className="min-h-0 flex-1 overflow-y-auto p-4">
          {error && <ErrorNotice text={error} onRetry={refresh} />}{" "}
          {!state && !error && (
            <Panel title="Loading saved application">
              <Empty text="Connecting to the local Python API…" />
            </Panel>
          )}
          {state && !state.profile && (
            <Panel title="Business setup">
              <Empty text="Save business details and choose your data to begin. No default business has been assigned." />
              <a className="m-4 inline-block text-accent underline" href="/">
                Set up your business
              </a>
            </Panel>
          )}
          {state && state.profile && (
            <>
              {nav === "overview" && timeline === "today" && (
                <TodayView
                  state={state}
                  refresh={refresh}
                  onAnalyse={() => setTimeline("rain")}
                />
              )}{" "}
              {nav === "overview" && timeline === "rain" && (
                <ScenarioView state={state} refresh={refresh} />
              )}{" "}
              {nav === "overview" && timeline === "year" && (
                <HistoryView state={state} />
              )}{" "}
              {nav === "protections" && (
                <ProtectionsPage state={state} refresh={refresh} />
              )}{" "}
              {nav === "risks" && <RisksPage state={state} />}{" "}
              {nav === "activity" && (
                <ActivityPage state={state} refresh={refresh} />
              )}{" "}
              {nav === "sources" && (
                <SourcesPage state={state} refresh={refresh} />
              )}{" "}
              {nav === "settings" && (
                <SettingsPage state={state} refresh={refresh} />
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
