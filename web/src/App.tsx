import { useState } from "react";

import { AccountsPanel } from "./components/AccountsPanel";
import { BudgetsPanel } from "./components/BudgetsPanel";
import { CategoriesPanel } from "./components/CategoriesPanel";
import { ConnectionsPanel } from "./components/ConnectionsPanel";
import { Hero } from "./components/Hero";
import { OverviewPanel } from "./components/OverviewPanel";
import { RulesPanel } from "./components/RulesPanel";
import { TransactionsPanel } from "./components/TransactionsPanel";
import { UnknownQueuePanel } from "./components/UnknownQueuePanel";
import { useBurnRateData } from "./hooks/useBurnRateData";

type WorkspaceTab = "dashboard" | "ledger" | "review" | "automation";

export default function App() {
  const data = useBurnRateData();
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("dashboard");

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
      label: "Ledger",
      caption: "Transactions and filters for the working month.",
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
      label: "Automation",
      caption: "Rules and monthly budgets.",
      badge: String(data.rules.length + data.budgets.length),
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
          <section className="top-grid">
            <OverviewPanel
              summary={data.summary}
              summaryLoading={data.summaryLoading}
              summaryError={data.summaryError}
              connections={data.connections.length}
              accounts={data.accounts.length}
              uncategorizedCount={data.uncategorizedCount}
              apiBase={data.apiBase}
              activeMonth={data.filters.month}
            />
            <ConnectionsPanel connections={data.connections} />
          </section>

          <section className="middle-grid">
            <AccountsPanel accounts={data.accounts} />
          </section>
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
        <section className="workspace-grid">
          <div className="workspace-stack">
            <UnknownQueuePanel
              transactions={data.unknownQueue.items}
              total={data.unknownQueue.total}
              loading={data.unknownQueue.loading}
              error={data.unknownQueue.error}
              paging={data.unknownPaging}
              categories={data.categories}
              onMovePage={data.moveUnknownPage}
              onAssign={data.categorizeTransaction}
            />
          </div>
          <CategoriesPanel categories={data.categories} onCreateCategory={data.createCategory} />
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
            onCreateBudget={data.createBudget}
            onUpdateBudget={data.updateBudget}
            onDeactivateBudget={data.deactivateBudget}
          />
        </section>
      ) : null}
    </main>
  );
}
