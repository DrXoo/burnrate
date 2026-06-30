import type { Account } from "../types";
import { formatDateTime } from "../lib/format";
import { Card } from "./ui/Card";
import { StatusTag } from "./ui/StatusTag";

interface AccountsPanelProps {
  accounts: Account[];
}

export function AccountsPanel({ accounts }: AccountsPanelProps) {
  return (
    <Card title="Accounts" subtitle="Balances, inclusion flags, and source metadata for imported ledgers.">
      <div className="stack">
        {accounts.length === 0 ? (
          <div className="empty-state">No imported accounts yet.</div>
        ) : (
          accounts.map((account) => (
            <article key={account.account_id} className="list-card">
              <div className="row">
                <strong>{account.display_name}</strong>
                <StatusTag>{account.latest_balance_amount || "0.00"} {account.latest_balance_currency || account.currency}</StatusTag>
              </div>
              <p className="meta-copy">
                {account.source_aspsp_name || "Manual / unknown source"}
                <br />
                Calculations: {account.included_in_calculations ? "included" : "excluded"} · Runway:{" "}
                {account.included_in_runway ? "included" : "excluded"}
                <br />
                Last synced: {formatDateTime(account.last_synced_at)}
              </p>
            </article>
          ))
        )}
      </div>
    </Card>
  );
}
