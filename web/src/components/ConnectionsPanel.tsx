import type { Connection } from "../types";
import { formatDateTime } from "../lib/format";
import { Card } from "./ui/Card";
import { StatusTag } from "./ui/StatusTag";

interface ConnectionsPanelProps {
  connections: Connection[];
}

export function ConnectionsPanel({ connections }: ConnectionsPanelProps) {
  return (
    <Card
      title="Connections"
      subtitle="Enable Banking sessions, sync health, and account linkage at a glance."
    >
      <div className="stack">
        {connections.length === 0 ? (
          <div className="empty-state">No bank connections yet.</div>
        ) : (
          connections.map((connection) => (
            <article key={connection.connection_id} className="list-card">
              <div className="row">
                <strong>
                  {connection.aspsp_name} <span className="muted">({connection.aspsp_country})</span>
                </strong>
                <StatusTag
                  tone={
                    connection.latest_sync_status === "success"
                      ? "good"
                      : connection.latest_sync_status === "failed"
                        ? "danger"
                        : "default"
                  }
                >
                  {connection.latest_sync_status || connection.session_status || "unknown"}
                </StatusTag>
              </div>
              <p className="meta-copy">
                {connection.psu_type} user · {connection.linked_account_count} linked account(s)
                <br />
                Session: {connection.session_id || "not stored"}
                <br />
                Last sync: {formatDateTime(connection.latest_sync_finished_at || connection.last_synced_at)}
              </p>
            </article>
          ))
        )}
      </div>
    </Card>
  );
}
