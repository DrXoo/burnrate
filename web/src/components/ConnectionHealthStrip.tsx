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

  return (
    <div className={healthy ? "success-banner" : "warn-banner"}>
      <div className="row">
        <span>
          {healthy
            ? `${connections.length} bank connection(s) healthy.`
            : `${attention.length} of ${connections.length} bank connection(s) need attention.`}
        </span>
        <button type="button" className="button button-secondary" onClick={onManage}>
          Manage connections
        </button>
      </div>
    </div>
  );
}
