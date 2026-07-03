import { useState } from "react";

import { IconSync } from "./icons";
import { TONE_COLOR, TONE_DIM, timeAgo } from "../lib/format";
import type { Tone } from "../lib/format";
import type { Connection } from "../types";

interface HealthStripProps {
  connection: Connection;
  onSync: (connectionId: string) => Promise<unknown>;
}

function connectionTone(connection: Connection): Tone {
  if (connection.latest_sync_error_summary) {
    return "over";
  }
  if (!connection.active) {
    return "watch";
  }
  return "good";
}

function connectionLabel(connection: Connection, tone: Tone): string {
  if (tone === "over") {
    return "Needs attention";
  }
  if (tone === "watch") {
    return "Inactive";
  }
  return "Healthy";
}

export function HealthStrip({ connection, onSync }: HealthStripProps) {
  const [syncing, setSyncing] = useState(false);
  const tone = connectionTone(connection);
  const color = TONE_COLOR[tone];
  const label = connectionLabel(connection, tone);
  const pendingCopy =
    connection.latest_sync_transactions_count != null
      ? `${connection.latest_sync_transactions_count} imported last sync — booked only`
      : "Booked transactions only";

  async function handleSync() {
    setSyncing(true);
    try {
      await onSync(connection.connection_id);
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div style={{ padding: "12px 30px 0" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "9px 14px",
          background: TONE_DIM[tone],
          border: `1px solid color-mix(in oklab, ${color} 25%, transparent)`,
          borderRadius: 10,
          flexWrap: "wrap",
        }}
      >
        <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12.5, fontWeight: 600, color }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, boxShadow: `0 0 8px ${color}` }} />
          {connection.aspsp_name} · {label}
        </span>
        <span style={{ fontSize: 12.5, color: "var(--text-2)" }}>Synced {timeAgo(connection.last_synced_at)}</span>
        <span style={{ fontSize: 12, color: "var(--text-3)" }}>{pendingCopy}</span>
        <button
          type="button"
          onClick={handleSync}
          disabled={syncing}
          style={{
            marginLeft: "auto",
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            border: "1px solid var(--line-2)",
            background: "var(--bg-3)",
            color: "var(--text)",
            borderRadius: 8,
            padding: "5px 11px",
            font: "500 12px 'Hanken Grotesque', sans-serif",
            cursor: syncing ? "default" : "pointer",
            opacity: syncing ? 0.6 : 1,
          }}
        >
          <IconSync />
          {syncing ? "Syncing…" : "Sync now"}
        </button>
      </div>
    </div>
  );
}
