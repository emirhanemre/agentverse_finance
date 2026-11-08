"use client";
import { useState } from "react";
import { Badge, Button, Panel } from "./ui";
import { api, message, stamp, type AppState } from "../lib/api";
import { ErrorNotice } from "./onboarding/Onboarding";
export default function Notifications({
  state,
  refresh,
}: {
  state: AppState;
  refresh: () => Promise<unknown>;
}) {
  const [error, setError] = useState("");
  const read = async (id: number) => {
    try {
      await api(`/notifications/${id}/read`, "POST");
      await refresh();
    } catch (e) {
      setError(message(e));
    }
  };
  return (
    <Panel
      title="Alerts"
      actions={
        <Badge tone="warning">
          {state.notifications.filter((n) => !n.read_at).length} unread
        </Badge>
      }
      bodyClassName="p-0"
    >
      {error && <ErrorNotice text={error} />}
      <ul className="divide-y divide-line">
        {state.notifications.map((n) => (
          <li
            key={n.id}
            className="flex items-start justify-between gap-4 px-4 py-3"
          >
            <div>
              <p
                className={
                  n.read_at
                    ? "text-[12.5px] text-fg-3"
                    : "text-[12.5px] text-fg"
                }
              >
                {n.message}
              </p>
              <p className="mt-1 font-mono text-[11px] text-fg-3">
                {stamp(n.created_at)} · {n.category}
              </p>
            </div>
            {!n.read_at && (
              <Button size="sm" onClick={() => read(n.id)}>
                Mark read
              </Button>
            )}
          </li>
        ))}
      </ul>
      {!state.notifications.length && (
        <p className="p-4 text-[12px] text-fg-3">
          No alerts yet. Training, monitoring, proposals and official paper
          resolutions appear here.
        </p>
      )}
    </Panel>
  );
}
