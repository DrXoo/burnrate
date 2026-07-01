import { useEffect, useState } from "react";

import { AccountsPanel } from "./components/AccountsPanel";
import { BudgetsPanel } from "./components/BudgetsPanel";
import { CategoriesPanel } from "./components/CategoriesPanel";
import { ConnectBankModal } from "./components/ConnectBankModal";
import { ConnectionHealthStrip } from "./components/ConnectionHealthStrip";
import { ConnectionsPanel } from "./components/ConnectionsPanel";
import { GettingStarted } from "./components/GettingStarted";
import { Hero } from "./components/Hero";
import { OverviewPanel } from "./components/OverviewPanel";
import { RulesPanel } from "./components/RulesPanel";
import { TransactionsPanel } from "./components/TransactionsPanel";
import { UnknownQueuePanel } from "./components/UnknownQueuePanel";
import { useBurnRateData } from "./hooks/useBurnRateData";

type WorkspaceTab = "dashboard" | "ledger" | "review" | "automation" | "settings";

interface ConnectResult {
  banner: "success-banner" | "warn-banner" | "error-banner";
  message: string;
}

export default function App() {
  const data = useBurnRateData();
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("dashboard");
  const [connectOpen, setConnectOpen] = useState(false);
  const [connectResult, setConnectResult] = useState<ConnectResult | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const connect = params.get("connect");
    if (!connect) {
      return;
    }
    if (connect === "success") {
      const accounts = params.get("accounts") ?? "0";
      const imported = params.get("imported") ?? "0";
      setConnectResult({
        banner: "success-banner",
        message: `Bank connected. Imported ${imported} transaction(s) across ${accounts} account(s).`,
      });
    } else if (connect === "empty") {
      setConnectResult({
        banner: "warn-banner",
        message:
          "Authorized, but no accounts were linked to this application (Enable Banking restricted production mode).",
      });
    } else if (connect === "error") {
      setConnectResult({
        banner: "error-banner",
        message: params.get("message") || "Bank connection failed.",
      });
    }
    // Strip the connect params so a refresh does not re-show the banner.
    window.history.replaceState({}, "", window.location.pathname);
  }, []);

  const overspentBudgetCount =
    data.summary?.budget_usage.filter((budget) => budget.status === "over").length ?? 0;

  const tabs: Array<{
    id: WorkspaceTab;
    label: string;
    caption: string;
    badge?: string;
  }> = [
    {
      id: "dashboard",
      label: "Dashboard",
      caption: "Summary, balances, and connection health.",
    },
    {
      id: "ledger",
      label: "Transactions",
      caption: "Imported transactions and filters for the working month.",
      badge: String(data.transactions.total),
    },
    {
      id: "review",
      label: "Review",
      caption: "Unknown queue and category cleanup.",
      badge: String(data.uncategorizedCount),
    },
    {
      id: "automation",
      label: "Rules & Budgets",
      caption: "Categorization rules and monthly budgets.",
      badge: overspentBudgetCount > 0 ? String(overspentBudgetCount) : undefined,
    },
    {
      id: "settings",
      label: "Settings",
      caption: "Bank connections, accounts, and categories.",
    },
  ];

  if (data.bootLoading) {
    return (
      <main className="app-shell">
        <Hero />
        <div className="loading-stage">
          <div className="loading-orb" />
          <p>Booting the workspace and locating the backend API...</p>
        </div>
      </main>
    );
  }

  if (data.bootError) {
    return (
      <main className="app-shell">
        <Hero />
        <section className="fatal-card">
          <h2>Backend detection failed</h2>
          <p>{data.bootError}</p>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <Hero />

      {connectResult ? (
        <div className={connectResult.banner}>
          <div className="row">
            <span>{connectResult.message}</span>
            <button
              type="button"
              className="modal-close"
              aria-label="Dismiss"
              onClick={() => setConnectResult(null)}
            >
              ×
            </button>
          </div>
        </div>
      ) : null}

      <section className="tab-shell">
        <div className="tab-row" role="tablist" aria-label="BurnRate workspace sections">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              className={`tab-button ${activeTab === tab.id ? "tab-button-active" : ""}`.trim()}
              onClick={() => setActiveTab(tab.id)}
            >
              <span className="tab-label-row">
                <span className="tab-label">{tab.label}</span>
                {tab.badge ? <span className="tab-badge">{tab.badge}</span> : null}
              </span>
              <span className="tab-caption">{tab.caption}</span>
            </button>
          ))}
        </div>
      </section>

      {activeTab === "dashboard" ? (
        <section className="tab-panel-stack">
          {data.connections.length === 0 && data.accounts.length === 0 ? (
            <GettingStarted onConnect={() => setConnectOpen(true)} />
          ) : null}
          <ConnectionHealthStrip connections={data.connections} onManage={() => setActiveTab("settings")} />
          <OverviewPanel
            summary={data.summary}
            summaryLoading={data.summaryLoading}
            summaryError={data.summaryError}
            uncategorizedCount={data.uncategorizedCount}
            apiBase={data.apiBase}
            activeMonth={data.filters.month}
          />
        </section>
      ) : null}

      {activeTab === "ledger" ? (
        <section className="tab-panel-stack">
          <TransactionsPanel
            accounts={data.accounts}
            categories={data.categories}
            filters={data.filters}
            paging={data.transactionsPaging}
            transactions={data.transactions.items}
            total={data.transactions.total}
            loading={data.transactions.loading}
            error={data.transactions.error}
            onApplyFilters={data.applyFilters}
            onMovePage={data.moveTransactionsPage}
            onAssignCategory={data.categorizeTransaction}
            onClearCategory={data.uncategorizeTransaction}
            onCreateRule={data.createRule}
          />
        </section>
      ) : null}

      {activeTab === "review" ? (
        <section className="tab-panel-stack">
          <UnknownQueuePanel
            transactions={data.unknownQueue.items}
            total={data.unknownQueue.total}
            loading={data.unknownQueue.loading}
            error={data.unknownQueue.error}
            paging={data.unknownPaging}
            categories={data.categories}
            onMovePage={data.moveUnknownPage}
            onAssignCategory={data.categorizeTransaction}
            onClearCategory={data.uncategorizeTransaction}
            onCreateRule={data.createRule}
          />
        </section>
      ) : null}

      {activeTab === "automation" ? (
        <section className="workspace-grid">
          <div className="workspace-stack">
            <RulesPanel rules={data.rules} onToggleRule={data.toggleRule} onUpdateRule={data.updateRule} />
          </div>
          <BudgetsPanel
            budgets={data.budgets}
            categories={data.categories}
            activeMonth={data.filters.month}
            onCreateBudget={data.createBudget}
            onUpdateBudget={data.updateBudget}
            onDeactivateBudget={data.deactivateBudget}
          />
        </section>
      ) : null}

      {activeTab === "settings" ? (
        <section className="tab-panel-stack">
          <ConnectionsPanel
            connections={data.connections}
            onSyncConnection={data.syncConnection}
            onConnect={() => setConnectOpen(true)}
          />
          <section className="workspace-grid">
            <AccountsPanel accounts={data.accounts} onUpdateAccount={data.updateAccount} />
            <CategoriesPanel categories={data.categories} onCreateCategory={data.createCategory} />
          </section>
        </section>
      ) : null}

      {connectOpen && data.apiBase ? (
        <ConnectBankModal apiBase={data.apiBase} onClose={() => setConnectOpen(false)} />
      ) : null}
    </main>
  );
}
