import { TONE_COLOR, TONE_DIM, expiryBadge, needsReconnect, nextSyncLabel, timeAgo } from "../lib/format";
import type { Tone } from "../lib/format";
import type { Connection } from "../types";

interface HealthStripProps {
  connection: Connection;
  /** When the backend says the next unattended sync is due, offset included. With no
      Sync button left, this is the owner's only answer to "when does this refresh?" */
  nextSyncAt: string | null | undefined;
  onReconnect: (connection: Connection) => void;
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

export function HealthStrip({ connection, nextSyncAt, onReconnect }: HealthStripProps) {
  const tone = connectionTone(connection);
  const color = TONE_COLOR[tone];
  const label = connectionLabel(connection, tone);
  const badge = expiryBadge(connection);
  const showReconnect = needsReconnect(connection);
  const pendingCopy =
    connection.latest_sync_transactions_count != null
      ? `${connection.latest_sync_transactions_count} imported last sync — booked only`
      : "Booked transactions only";

  // Only while healthy, and the suppression is the point rather than tidiness: the
  // schedule says what the worker *intends*, and a worker that is not running cannot
  // contradict it. Printing "next at 21:00" above "Needs attention" would reassure the
  // owner at exactly the moment it should not. ADR-0013 records the half of this that
  // is still open -- a worker that dies between successful passes leaves this line
  // standing until the sync-gap alert notices.
  const nextSync = tone === "good" ? nextSyncLabel(nextSyncAt) : null;

  return (
    <div className="br-health" style={{ padding: "12px 30px 0" }}>
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
        <span style={{ fontSize: 12.5, color: "var(--text-2)" }}>
          Synced {timeAgo(connection.last_synced_at)}
          {nextSync ? ` · next at ${nextSync}` : ""}
        </span>
        <span style={{ fontSize: 12, color: "var(--text-3)" }}>{pendingCopy}</span>
        {badge ? (
          <span
            style={{
              fontSize: 11.5,
              fontWeight: 600,
              color: TONE_COLOR[badge.tone],
              background: TONE_DIM[badge.tone],
              border: `1px solid color-mix(in oklab, ${TONE_COLOR[badge.tone]} 30%, transparent)`,
              borderRadius: 99,
              padding: "2px 9px",
            }}
          >
            {badge.text}
          </span>
        ) : null}
        <div style={{ marginLeft: "auto", display: "inline-flex", gap: 8 }}>
          {showReconnect ? (
            <button
              type="button"
              onClick={() => onReconnect(connection)}
              style={{
                border: "none",
                background: "var(--accent)",
                color: "#0a0d10",
                borderRadius: 8,
                padding: "5px 12px",
                font: "600 12px 'Hanken Grotesque', sans-serif",
                cursor: "pointer",
              }}
            >
              Reconnect
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
