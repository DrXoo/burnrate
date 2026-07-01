import { formatDateTime } from "../lib/format";
import type { Connection } from "../types";

interface ConnectionHealthStripProps {
  connections: Connection[];
  onManage: () => void;
}

function needsAttention(connection: Connection): boolean {
  if (!connection.active) {
    return true;
  }
  if (connection.latest_sync_status === "failed") {
    return true;
  }
  const authorized = (connection.session_status ?? "").toUpperCase() === "AUTHORIZED";
  return authorized && connection.linked_account_count === 0;
}

export function ConnectionHealthStrip({ connections, onManage }: ConnectionHealthStripProps) {
  if (connections.length === 0) {
    return null;
  }

  const attention = connections.filter(needsAttention);
  const healthy = attention.length === 0;
  const lastSynced = connections
    .map((connection) => connection.last_synced_at)
    .filter((value): value is string => Boolean(value))
    .sort()
    .at(-1);

  const summary = healthy
    ? `${connections.length} bank connection(s) healthy.`
    : `${attention.length} of ${connections.length} bank connection(s) need attention.`;

  return (
    <div className={healthy ? "success-banner" : "warn-banner"}>
      <div className="row">
        <span>
          {summary}
          {lastSynced ? ` · Last synced ${formatDateTime(lastSynced)}` : ""}
        </span>
        <button type="button" className="button button-secondary" onClick={onManage}>
          Manage connections
        </button>
      </div>
    </div>
  );
}
