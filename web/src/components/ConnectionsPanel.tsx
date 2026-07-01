import { useEffect, useState } from "react";

import { formatDateTime } from "../lib/format";
import type { Connection, ManualSyncResult } from "../types";
import { Card } from "./ui/Card";
import { StatusTag } from "./ui/StatusTag";

interface ConnectionsPanelProps {
  connections: Connection[];
  onSyncConnection: (connectionId: string) => Promise<ManualSyncResult>;
}

interface ConnectionCardProps {
  connection: Connection;
  onSyncConnection: ConnectionsPanelProps["onSyncConnection"];
}

function syncTone(connection: Connection): "default" | "good" | "warn" | "danger" {
  if (!connection.active) {
    return "danger";
  }
  if (connection.latest_sync_status === "failed") {
    return "danger";
  }
  if (connection.latest_sync_status === "skipped") {
    return "warn";
  }
  if (connection.latest_sync_status === "success") {
    return "good";
  }
  if (connection.session_status && connection.session_status !== "AUTHORIZED") {
    return "warn";
  }
  return "default";
}

function ConnectionCard({ connection, onSyncConnection }: ConnectionCardProps) {
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setBusy(false);
  }, [connection.latest_sync_finished_at, connection.latest_sync_status, connection.latest_sync_transactions_count]);

  async function handleSync() {
    try {
      setBusy(true);
      setError(null);
      const result = await onSyncConnection(connection.connection_id);
      setFeedback(
        `${result.accounts_synced} account(s) synced, ${result.transactions_imported} transaction(s) imported${
          result.message ? `, ${result.message}` : ""
        }.`,
      );
      setBusy(false);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
      setBusy(false);
    }
  }

  const showRestrictedEmpty =
    connection.active &&
    (connection.session_status ?? "").toUpperCase() === "AUTHORIZED" &&
    connection.linked_account_count === 0;

  return (
    <article className="list-card">
      <div className="row">
        <strong>
          {connection.aspsp_name} <span className="muted">({connection.aspsp_country})</span>
        </strong>
        <StatusTag tone={syncTone(connection)}>
          {!connection.active
            ? "needs reconnection"
            : connection.latest_sync_status || connection.session_status || "unknown"}
        </StatusTag>
      </div>
      <p className="meta-copy">
        {connection.psu_type} user · {connection.linked_account_count} linked account(s)
        <br />
        Session: {connection.session_id || "not stored"} · Status: {connection.session_status || "unknown"}
        <br />
        Last sync finished: {formatDateTime(connection.latest_sync_finished_at || connection.last_synced_at)}
      </p>

      <div className="connection-metric-grid">
        <article className="mini-metric">
          <span className="stat-label">Accounts synced</span>
          <strong>{connection.latest_sync_accounts_count ?? 0}</strong>
        </article>
        <article className="mini-metric">
          <span className="stat-label">Transactions imported</span>
          <strong>{connection.latest_sync_transactions_count ?? 0}</strong>
        </article>
      </div>

      <div className="inline-actions">
        <button type="button" className="button" disabled={busy || !connection.active} onClick={handleSync}>
          {busy ? "Syncing..." : "Sync now"}
        </button>
        {connection.latest_sync_started_at ? (
          <span className="glass-pill">Started {formatDateTime(connection.latest_sync_started_at)}</span>
        ) : null}
      </div>

      {!connection.active ? (
        <div className="warn-banner">
          {connection.latest_sync_error_summary ||
            "This connection is inactive and must be re-authorized before syncing can resume."}
        </div>
      ) : connection.latest_sync_error_summary ? (
        connection.latest_sync_status === "skipped" ? (
          <div className="warn-banner">{connection.latest_sync_error_summary}</div>
        ) : (
          <div className="error-banner">Latest sync error: {connection.latest_sync_error_summary}</div>
        )
      ) : null}
      {showRestrictedEmpty ? (
        <div className="warn-banner">
          Authorized, but no accounts are linked to this BurnRate application. In restricted production mode
          Enable Banking only returns accounts that were pre-linked — the account you authorized may not be one
          of them.
        </div>
      ) : null}
      {feedback ? <div className="success-banner">{feedback}</div> : null}
      {error ? <div className="error-banner">{error}</div> : null}
    </article>
  );
}

export function ConnectionsPanel({ connections, onSyncConnection }: ConnectionsPanelProps) {
  return (
    <Card
      title="Connections"
      subtitle="Enable Banking sessions, sync health, and manual re-sync controls in one place."
    >
      <div className="stack">
        {connections.length === 0 ? (
          <div className="empty-state">
            No bank connections yet. Connect a bank account to start importing balances and transactions. In-app
            linking is coming soon.
          </div>
        ) : (
          connections.map((connection) => (
            <ConnectionCard
              key={connection.connection_id}
              connection={connection}
              onSyncConnection={onSyncConnection}
            />
          ))
        )}
      </div>
    </Card>
  );
}
