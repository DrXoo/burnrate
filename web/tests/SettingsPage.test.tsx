import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SettingsPage } from "../src/components/pages/SettingsPage";
import type { Account } from "../src/types";

function account(overrides: Partial<Account>): Account {
  return {
    account_id: "acc-1",
    display_name: "GARCIA ROMERO DOMINGO",
    currency: "EUR",
    latest_balance_amount: "1701.54",
    latest_balance_currency: "EUR",
    included_in_calculations: true,
    last_synced_at: "2026-11-05T11:00:24Z",
    source_connection_id: "conn-openbank",
    source_aspsp_name: "Openbank",
    source_aspsp_country: "ES",
    external_account_id: "81eb8809",
    ...overrides,
  };
}

function markup(accounts: Account[]) {
  return renderToStaticMarkup(
    <SettingsPage
      connections={[]}
      accounts={accounts}
      onConnect={() => {}}
      onReconnect={() => {}}
      onUpdateAccount={async () => {}}
    />,
  );
}

describe("SettingsPage — telling two accounts apart", () => {
  it("names the bank each account came from", () => {
    // A display name is the account *holder*, not the account, so a person with two
    // accounts at one bank gets two rows reading exactly the same. The owner counted
    // three such rows as two banks -- and that counting is what verifies a
    // reconnection did not duplicate an account, since Enable Banking issues a new
    // per-session uid each time and only a hash match prevents a second row.
    const html = markup([
      account({ account_id: "acc-1" }),
      account({ account_id: "acc-2", latest_balance_amount: "0.00" }),
      account({
        account_id: "acc-3",
        display_name: "DOMINGO GARCIA ROMERO && YORLING ADELINA OPORTA OJEDA",
        latest_balance_amount: "49.54",
        source_aspsp_name: "ING",
        source_connection_id: "conn-ing",
      }),
    ]);

    // Matched against the whole meta line rather than the bank name alone: a bare
    // /ING/ also hits the holder name "YORLING", which made the first version of this
    // test fail against correct output.
    expect(html.match(/Openbank · €/g)).toHaveLength(2);
    expect(html).toContain("ING · €49.54");
    expect(html).toContain("Openbank · €0.00");
  });

  it("says so when an account belongs to no connection", () => {
    // `source_aspsp_name` is null for an account with no mapping -- a bank whose
    // connection was replaced, or a manually added account when those arrive. Naming
    // it is the point: a blank where every other row names a bank reads as a
    // rendering fault rather than as a fact about that account.
    const html = markup([account({ source_aspsp_name: null, source_connection_id: null })]);

    expect(html).toContain("Not linked to a bank");
  });
});
