import { useState, type CSSProperties } from "react";

import { TONE_COLOR, TONE_DIM, eur, expiryBadge, needsReconnect, timeAgo } from "../../lib/format";
import type { Account, Connection } from "../../types";

interface SettingsPageProps {
  connections: Connection[];
  accounts: Account[];
  onSyncConnection: (connectionId: string) => Promise<unknown>;
  onConnect: () => void;
  onReconnect: (connection: Connection) => void;
  onUpdateAccount: (accountId: string, draft: Pick<Account, "included_in_calculations">) => Promise<void>;
}

const cardStyle: CSSProperties = {
  background: "var(--bg-2)",
  border: "1px solid var(--line)",
  borderRadius: 16,
  padding: "20px 22px",
  boxShadow: "var(--card-shadow)",
};

function chip(active: boolean, tone: "accent" | "good"): CSSProperties {
  const color = tone === "good" ? "var(--good)" : "var(--accent)";
  return {
    fontSize: 11,
    fontWeight: 600,
    padding: "4px 10px",
    borderRadius: 99,
    cursor: "pointer",
    border: `1px solid ${active ? `color-mix(in oklab, ${color} 45%, transparent)` : "var(--line-2)"}`,
    background: active ? (tone === "good" ? "var(--good-dim)" : "color-mix(in oklab, var(--accent) 16%, transparent)") : "transparent",
    color: active ? color : "var(--text-3)",
  };
}

function ConnectionRow({
  connection,
  onSync,
  onReconnect,
}: {
  connection: Connection;
  onSync: (id: string) => Promise<unknown>;
  onReconnect: (connection: Connection) => void;
}) {
  const [syncing, setSyncing] = useState(false);
  const healthy = connection.active && !connection.latest_sync_error_summary;
  const statusColor = healthy ? "var(--good)" : "var(--over)";
  const badge = expiryBadge(connection);
  const showReconnect = needsReconnect(connection);

  async function handleSync() {
    setSyncing(true);
    try {
      await onSync(connection.connection_id);
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, padding: 14, background: "var(--bg-3)", border: "1px solid var(--line)", borderRadius: 12 }}>
      <div style={{ width: 40, height: 40, borderRadius: 10, background: "var(--bg-4)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 15, color: "var(--text-2)" }}>
        {connection.aspsp_name.charAt(0).toUpperCase()}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
          {connection.aspsp_name}
          {badge ? (
            <span
              style={{
                fontSize: 10.5,
                fontWeight: 600,
                color: TONE_COLOR[badge.tone],
                background: TONE_DIM[badge.tone],
                border: `1px solid color-mix(in oklab, ${TONE_COLOR[badge.tone]} 30%, transparent)`,
                borderRadius: 99,
                padding: "1px 8px",
              }}
            >
              {badge.text}
            </span>
          ) : null}
        </div>
        <div style={{ fontSize: 12, color: statusColor, fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: statusColor }} />
          {healthy ? "Healthy" : "Needs attention"} · synced {timeAgo(connection.last_synced_at)}
        </div>
      </div>
      {showReconnect ? (
        <button
          type="button"
          onClick={() => onReconnect(connection)}
          style={{ border: "none", background: "var(--accent)", color: "#0a0d10", borderRadius: 8, padding: "6px 12px", font: "600 12px 'Hanken Grotesque', sans-serif", cursor: "pointer" }}
        >
          Reconnect
        </button>
      ) : null}
      <button
        type="button"
        onClick={handleSync}
        disabled={syncing}
        style={{ border: "1px solid var(--line-2)", background: "var(--bg-2)", color: "var(--text)", borderRadius: 8, padding: "6px 12px", font: "500 12px 'Hanken Grotesque', sans-serif", cursor: syncing ? "default" : "pointer", opacity: syncing ? 0.6 : 1 }}
      >
        {syncing ? "Syncing…" : "Sync"}
      </button>
    </div>
  );
}

export function SettingsPage({ connections, accounts, onSyncConnection, onConnect, onReconnect, onUpdateAccount }: SettingsPageProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, maxWidth: 760 }}>
      <div style={cardStyle}>
        <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Bank connections</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {connections.length === 0 ? (
            <div style={{ padding: 18, textAlign: "center", color: "var(--text-3)", fontSize: 13, background: "var(--bg-3)", borderRadius: 12 }}>
              No banks connected yet.
            </div>
          ) : (
            connections.map((connection) => (
              <ConnectionRow key={connection.connection_id} connection={connection} onSync={onSyncConnection} onReconnect={onReconnect} />
            ))
          )}
        </div>
        <button
          type="button"
          onClick={onConnect}
          style={{ marginTop: 12, width: "100%", padding: 11, border: "1px dashed var(--line-2)", background: "transparent", color: "var(--text-2)", borderRadius: 11, font: "500 13px 'Hanken Grotesque', sans-serif", cursor: "pointer" }}
        >
          + Connect a bank
        </button>
      </div>

      <div style={cardStyle}>
        <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>Accounts</div>
        <div style={{ fontSize: 12.5, color: "var(--text-3)", marginBottom: 14 }}>
          Toggle which accounts feed your balance and spending.
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {accounts.length === 0 ? (
            <div style={{ padding: 18, textAlign: "center", color: "var(--text-3)", fontSize: 13, background: "var(--bg-3)", borderRadius: 11 }}>
              No accounts linked yet.
            </div>
          ) : (
            accounts.map((account) => (
              <div key={account.account_id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px", background: "var(--bg-3)", border: "1px solid var(--line)", borderRadius: 11 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 500 }}>{account.display_name}</div>
                  <div className="num" style={{ fontSize: 12, color: "var(--text-3)" }}>
                    {account.latest_balance_amount != null ? eur(account.latest_balance_amount) : "—"}
                  </div>
                </div>
                <button
                  type="button"
                  title="Include this account in balance and spending"
                  style={chip(account.included_in_calculations, "accent")}
                  onClick={() =>
                    void onUpdateAccount(account.account_id, {
                      included_in_calculations: !account.included_in_calculations,
                    })
                  }
                >
                  Included
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
