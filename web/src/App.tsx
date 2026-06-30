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

export default function App() {
  const data = useBurnRateData();

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

      <section className="top-grid">
        <OverviewPanel
          connections={data.connections.length}
          accounts={data.accounts.length}
          uncategorizedCount={data.uncategorizedCount}
          apiBase={data.apiBase}
        />
        <ConnectionsPanel connections={data.connections} />
      </section>

      <section className="middle-grid">
        <AccountsPanel accounts={data.accounts} />
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

      <section className="workspace-grid">
        <div className="workspace-stack">
          <CategoriesPanel categories={data.categories} onCreateCategory={data.createCategory} />
          <RulesPanel rules={data.rules} onToggleRule={data.toggleRule} onUpdateRule={data.updateRule} />
          <BudgetsPanel
            budgets={data.budgets}
            categories={data.categories}
            onCreateBudget={data.createBudget}
            onUpdateBudget={data.updateBudget}
            onDeactivateBudget={data.deactivateBudget}
          />
        </div>
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
      </section>
    </main>
  );
}
