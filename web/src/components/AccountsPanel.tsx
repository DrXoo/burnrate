import { useState } from "react";

import type { Account } from "../types";
import { formatDateTime } from "../lib/format";
import { Card } from "./ui/Card";
import { StatusTag } from "./ui/StatusTag";

interface AccountsPanelProps {
  accounts: Account[];
  onUpdateAccount: (
    accountId: string,
    draft: Pick<Account, "included_in_calculations" | "included_in_runway">,
  ) => Promise<void>;
}

interface AccountControlCardProps {
  account: Account;
  onUpdateAccount: AccountsPanelProps["onUpdateAccount"];
}

function AccountControlCard({ account, onUpdateAccount }: AccountControlCardProps) {
  const [busy, setBusy] = useState<"calculations" | "runway" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleToggle(nextCalculations: boolean, nextRunway: boolean, action: "calculations" | "runway") {
    try {
      setBusy(action);
      setError(null);
      await onUpdateAccount(account.account_id, {
        included_in_calculations: nextCalculations,
        included_in_runway: nextRunway,
      });
      setBusy(null);
    } catch (nextError) {
      setBusy(null);
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    }
  }

  return (
    <article className="list-card">
      <div className="row">
        <strong>{account.display_name}</strong>
        <StatusTag>
          {account.latest_balance_amount || "0.00"} {account.latest_balance_currency || account.currency}
        </StatusTag>
      </div>
      <p className="meta-copy">
        {account.source_aspsp_name || "Manual / unknown source"}
        <br />
        Last synced: {formatDateTime(account.last_synced_at)}
      </p>

      <div className="account-control-grid">
        <label className="toggle-card">
          <span>
            <strong>Include in calculations</strong>
            <span className="toggle-copy">Controls balances, spending, and money-left metrics.</span>
          </span>
          <input
            type="checkbox"
            checked={account.included_in_calculations}
            disabled={busy !== null}
            onChange={(event) =>
              void handleToggle(
                event.target.checked,
                event.target.checked ? account.included_in_runway : false,
                "calculations",
              )
            }
          />
        </label>

        <label className="toggle-card">
          <span>
            <strong>Include in runway</strong>
            <span className="toggle-copy">Only selected reserve accounts should count here.</span>
          </span>
          <input
            type="checkbox"
            checked={account.included_in_runway}
            disabled={busy !== null || !account.included_in_calculations}
            onChange={(event) =>
              void handleToggle(
                event.target.checked ? true : account.included_in_calculations,
                event.target.checked,
                "runway",
              )
            }
          />
        </label>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}
    </article>
  );
}

export function AccountsPanel({ accounts, onUpdateAccount }: AccountsPanelProps) {
  return (
    <Card title="Accounts" subtitle="Balances, inclusion flags, and source metadata for imported ledgers.">
      <div className="stack">
        {accounts.length === 0 ? (
          <div className="empty-state">
            No imported accounts yet. Once a bank connection is linked and synced, your accounts and balances
            appear here.
          </div>
        ) : (
          accounts.map((account) => (
            <AccountControlCard
              key={account.account_id}
              account={account}
              onUpdateAccount={onUpdateAccount}
            />
          ))
        )}
      </div>
    </Card>
  );
}
