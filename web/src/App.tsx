import { useEffect, useRef, useState } from "react";

import { ConnectBankModal } from "./components/ConnectBankModal";
import { FirstRun } from "./components/FirstRun";
import { HealthStrip } from "./components/HealthStrip";
import { Sidebar } from "./components/Sidebar";
import { Toast } from "./components/Toast";
import { TopBar } from "./components/TopBar";
import { CategoriesPage } from "./components/pages/CategoriesPage";
import { DashboardPage } from "./components/pages/DashboardPage";
import { ReviewPage } from "./components/pages/ReviewPage";
import { RulesBudgetsPage } from "./components/pages/RulesBudgetsPage";
import { SettingsPage } from "./components/pages/SettingsPage";
import { TransactionsPage } from "./components/pages/TransactionsPage";
import { useBurnRateData } from "./hooks/useBurnRateData";
import { formatMonthLabel } from "./lib/format";
import type { HeroMode, Section, Theme } from "./lib/viewTypes";

interface ToastState {
  message: string;
  tone: "good" | "over";
}

function CenteredNotice({ title, body, tone }: { title: string; body: string; tone: "neutral" | "over" }) {
  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 40 }}>
      <div style={{ maxWidth: 420, textAlign: "center" }}>
        <div className="num" style={{ fontSize: 20, fontWeight: 600, marginBottom: 8, color: tone === "over" ? "var(--over)" : "var(--text)" }}>
          {title}
        </div>
        <p style={{ fontSize: 14, color: "var(--text-2)", lineHeight: 1.6, margin: 0 }}>{body}</p>
      </div>
    </div>
  );
}

export default function App() {
  const data = useBurnRateData();
  const [section, setSection] = useState<Section>("dashboard");
  const [theme, setTheme] = useState<Theme>("dark");
  const [heroMode, setHeroMode] = useState<HeroMode>("dial");
  const [connectOpen, setConnectOpen] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);
  const toastTimer = useRef<number | null>(null);

  function showToast(message: string, tone: "good" | "over" = "good") {
    if (toastTimer.current) {
      window.clearTimeout(toastTimer.current);
    }
    setToast({ message, tone });
    toastTimer.current = window.setTimeout(() => setToast(null), 2200);
  }

  // Apply the theme at the document root so tokens cascade to fixed toasts/modals too.
  useEffect(() => {
    if (theme === "light") {
      document.documentElement.setAttribute("data-theme", "light");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  }, [theme]);

  // Surface the bank-connect redirect result (?connect=...) as a toast, then clean the URL.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const connect = params.get("connect");
    if (!connect) {
      return;
    }
    if (connect === "success") {
      const accounts = params.get("accounts") ?? "0";
      const imported = params.get("imported") ?? "0";
      showToast(`Bank connected — imported ${imported} transaction(s) across ${accounts} account(s).`);
    } else if (connect === "empty") {
      showToast("Authorized, but no accounts were linked (Enable Banking restricted production).", "over");
    } else if (connect === "error") {
      showToast(params.get("message") || "Bank connection failed.", "over");
    }
    window.history.replaceState({}, "", window.location.pathname);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const monthLabel = formatMonthLabel(data.filters.month);
  const includedAccountCount = data.accounts.filter((account) => account.included_in_calculations).length;

  function openConnect() {
    setConnectOpen(true);
  }

  // Wrap data-layer actions so successful edits fire a confirmation toast.
  async function categorize(transactionId: string, categoryId: string) {
    await data.categorizeTransaction(transactionId, categoryId);
    const category = data.categories.find((entry) => entry.category_id === categoryId);
    showToast(category ? `Categorized as ${category.name}` : "Categorized");
  }
  async function uncategorize(transactionId: string) {
    await data.uncategorizeTransaction(transactionId);
    showToast("Moved back to the queue");
  }
  async function createRule(transactionId: string, draft: Parameters<typeof data.createRule>[1]) {
    await data.createRule(transactionId, draft);
    showToast("Rule created");
  }
  async function toggleRule(ruleId: string, active: boolean) {
    await data.toggleRule(ruleId, active);
    showToast(active ? "Rule enabled" : "Rule disabled");
  }
  async function updateRule(ruleId: string, draft: Parameters<typeof data.updateRule>[1]) {
    await data.updateRule(ruleId, draft);
    showToast("Rule updated");
  }
  async function deleteRule(ruleId: string) {
    await data.deleteRule(ruleId);
    showToast("Rule deleted");
  }
  async function createBudget(draft: Parameters<typeof data.createBudget>[0]) {
    await data.createBudget(draft);
    showToast("Budget added");
  }
  async function updateBudget(budgetId: string, draft: Parameters<typeof data.updateBudget>[1]) {
    await data.updateBudget(budgetId, draft);
    showToast("Budget updated");
  }
  async function deactivateBudget(budgetId: string) {
    await data.deactivateBudget(budgetId);
    showToast("Budget removed");
  }
  async function createCategory(name: string, type: Parameters<typeof data.createCategory>[1]) {
    await data.createCategory(name, type);
    showToast(`Category “${name}” created`);
  }
  async function updateAccount(accountId: string, draft: Parameters<typeof data.updateAccount>[1]) {
    await data.updateAccount(accountId, draft);
    showToast("Account updated");
  }
  async function syncConnection(connectionId: string) {
    const result = await data.syncConnection(connectionId);
    showToast(result?.message || "Synced — booked transactions only");
    return result;
  }

  const modal = connectOpen && data.apiBase ? <ConnectBankModal apiBase={data.apiBase} onClose={() => setConnectOpen(false)} /> : null;
  const toastNode = toast ? <Toast message={toast.message} tone={toast.tone} /> : null;

  if (data.bootLoading) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
        <CenteredNotice title="Starting BurnRate…" body="Locating the backend API and loading your workspace." tone="neutral" />
      </div>
    );
  }

  if (data.bootError) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
        <CenteredNotice title="Backend detection failed" body={data.bootError} tone="over" />
      </div>
    );
  }

  const isFirstRun = data.connections.length === 0 && data.accounts.length === 0;
  if (isFirstRun) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
        <FirstRun onConnect={openConnect} />
        {modal}
        {toastNode}
      </div>
    );
  }

  const primaryConnection = data.connections[0];

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
      <div style={{ display: "flex", minHeight: "100vh" }}>
        <Sidebar section={section} reviewCount={data.uncategorizedCount} onNavigate={setSection} />

        <main className="br-scroll" style={{ flex: 1, minWidth: 0, height: "100vh", overflowY: "auto" }}>
          <TopBar
            section={section}
            monthLabel={monthLabel}
            theme={theme}
            heroMode={heroMode}
            onToggleTheme={() => setTheme((value) => (value === "dark" ? "light" : "dark"))}
            onSetHeroMode={setHeroMode}
          />

          {primaryConnection ? <HealthStrip connection={primaryConnection} onSync={syncConnection} /> : null}

          <div style={{ padding: "22px 30px 60px", maxWidth: 1160 }}>
            {section === "dashboard" ? (
              <DashboardPage
                summary={data.summary}
                loading={data.summaryLoading}
                error={data.summaryError}
                heroMode={heroMode}
                includedAccountCount={includedAccountCount}
              />
            ) : null}

            {section === "transactions" ? (
              <TransactionsPage
                accounts={data.accounts}
                categories={data.categories}
                rules={data.rules}
                filters={data.filters}
                applyFilters={data.applyFilters}
                items={data.transactions.items}
                total={data.transactions.total}
                loading={data.transactions.loading}
                error={data.transactions.error}
                paging={data.transactionsPaging}
                monthLabel={monthLabel}
                onMovePage={data.moveTransactionsPage}
                onCategorize={categorize}
                onUncategorize={uncategorize}
                onCreateRule={createRule}
                onUpdateRule={updateRule}
                onDeleteRule={deleteRule}
              />
            ) : null}

            {section === "review" ? (
              <ReviewPage
                items={data.unknownQueue.items}
                total={data.unknownQueue.total}
                loading={data.unknownQueue.loading}
                error={data.unknownQueue.error}
                paging={data.unknownPaging}
                categories={data.categories}
                onMovePage={data.moveUnknownPage}
                onCategorize={categorize}
              />
            ) : null}

            {section === "categories" ? (
              <CategoriesPage
                categories={data.categories}
                budgets={data.budgets}
                summary={data.summary}
                month={data.filters.month}
                monthLabel={monthLabel}
                loadMonthTransactions={data.listMonthTransactions}
                onCreateCategory={createCategory}
              />
            ) : null}

            {section === "rules" ? (
              <RulesBudgetsPage
                rules={data.rules}
                categories={data.categories}
                budgets={data.budgets}
                summary={data.summary}
                onToggleRule={toggleRule}
                onUpdateRule={updateRule}
                onDeleteRule={deleteRule}
                onCreateBudget={createBudget}
                onUpdateBudget={updateBudget}
                onDeactivateBudget={deactivateBudget}
              />
            ) : null}

            {section === "settings" ? (
              <SettingsPage
                connections={data.connections}
                accounts={data.accounts}
                onSyncConnection={syncConnection}
                onConnect={openConnect}
                onUpdateAccount={updateAccount}
              />
            ) : null}
          </div>
        </main>
      </div>

      {modal}
      {toastNode}
    </div>
  );
}
