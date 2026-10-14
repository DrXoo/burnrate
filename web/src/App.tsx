import { useEffect, useRef, useState } from "react";

import { ConnectBankModal, type ReconnectPrefill } from "./components/ConnectBankModal";
import { FirstRun } from "./components/FirstRun";
import { HealthStrip } from "./components/HealthStrip";
import { Login } from "./components/Login";
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
import type { Connection } from "./types";

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
  // A refresh that fails after an edit succeeded is reported here as well as on the
  // dashboard: the toast tells the owner their change landed and the figures did not,
  // which the banner alone cannot say.
  const data = useBurnRateData({
    onRefreshFailed: (message) => showToast(`Could not refresh the figures — ${message}`, "over"),
  });
  const [section, setSection] = useState<Section>("dashboard");
  const [theme, setTheme] = useState<Theme>("dark");
  const [heroMode, setHeroMode] = useState<HeroMode>("dial");
  const [connectOpen, setConnectOpen] = useState(false);
  const [connectPrefill, setConnectPrefill] = useState<ReconnectPrefill | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
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

  // The month is unknown for a moment on the first load and after a reset, while the
  // backend answers which one is current. Every month-scoped page is in its loading state
  // then, so the label says as much rather than reading blank. If that answer failed the
  // month stays unknown, and the label is the only control that can ask again -- the
  // arrows are disabled without a month to step from -- so it says so.
  const monthLabel = data.filters.month
    ? formatMonthLabel(data.filters.month)
    : data.summaryError
      ? "Month unavailable — retry"
      : "Loading month…";
  const includedAccountCount = data.accounts.filter((account) => account.included_in_calculations).length;

  function openConnect() {
    setConnectPrefill(null);
    setConnectOpen(true);
  }

  function openReconnect(connection: Connection) {
    setConnectPrefill({
      country: connection.aspsp_country,
      aspspName: connection.aspsp_name,
      psuType: connection.psu_type === "business" ? "business" : "personal",
    });
    setConnectOpen(true);
  }

  function closeConnect() {
    setConnectOpen(false);
    setConnectPrefill(null);
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
  async function exclude(transactionId: string) {
    await data.excludeTransaction(transactionId);
    showToast("Ignored — excluded from the budget");
  }
  async function restore(transactionId: string) {
    await data.restoreTransaction(transactionId);
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
    // "Removed" claimed more than happened: the row stays, and the months it covered
    // keep it. Cancelling is what the owner did, and it is undoable.
    showToast("Budget cancelled");
  }
  async function reactivateBudget(budgetId: string) {
    await data.reactivateBudget(budgetId);
    showToast("Budget reactivated");
  }
  async function createCategory(name: string, type: Parameters<typeof data.createCategory>[1]) {
    await data.createCategory(name, type);
    showToast(`Category “${name}” created`);
  }
  async function renameCategory(categoryId: string, name: string) {
    // Rethrown, not toasted: the caller keeps its editor open on the reason -- a name
    // already in use is the owner's to resolve, and a toast that fades takes the
    // reason with it.
    await data.renameCategory(categoryId, name);
    showToast(`Renamed to “${name}”`);
  }
  async function deleteCategory(categoryId: string) {
    // Rethrown like renameCategory: the Categories panel keeps the refusal on screen,
    // because it names the transactions, budgets or rules still pointing at it.
    await data.deleteCategory(categoryId);
    showToast("Category deleted");
  }
  async function archiveCategory(categoryId: string) {
    await data.archiveCategory(categoryId);
    showToast("Category archived");
  }
  async function unarchiveCategory(categoryId: string) {
    await data.unarchiveCategory(categoryId);
    showToast("Category unarchived");
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

  const modal = connectOpen && data.apiBase ? <ConnectBankModal apiBase={data.apiBase} prefill={connectPrefill} onClose={closeConnect} /> : null;
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

  if (data.authStatus === "unauthenticated") {
    return <Login onSubmit={data.login} />;
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
        <Sidebar
          section={section}
          reviewCount={data.uncategorizedCount}
          isOpen={menuOpen}
          onNavigate={(next) => {
            setSection(next);
            setMenuOpen(false);
          }}
        />
        {menuOpen ? <div className="br-overlay" onClick={() => setMenuOpen(false)} /> : null}

        <main className="br-scroll" style={{ flex: 1, minWidth: 0, height: "100vh", overflowY: "auto" }}>
          <TopBar
            section={section}
            month={data.filters.month}
            monthLabel={monthLabel}
            onSelectMonth={(month) => data.applyFilters({ ...data.filters, month })}
            theme={theme}
            heroMode={heroMode}
            onToggleTheme={() => setTheme((value) => (value === "dark" ? "light" : "dark"))}
            onSetHeroMode={setHeroMode}
            onToggleMenu={() => setMenuOpen((value) => !value)}
            onLogout={() => void data.logout()}
          />

          {primaryConnection ? <HealthStrip connection={primaryConnection} onSync={syncConnection} onReconnect={openReconnect} /> : null}

          <div className="br-content" style={{ padding: "22px 30px 60px" }}>
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
                assignableCategories={data.assignableCategories}
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
                onExclude={exclude}
                onRestore={restore}
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
                assignableCategories={data.assignableCategories}
                onMovePage={data.moveUnknownPage}
                onCategorize={categorize}
                onExclude={exclude}
              />
            ) : null}

            {section === "categories" ? (
              <CategoriesPage
                categories={data.categories}
                summary={data.summary}
                loading={data.summaryLoading}
                error={data.summaryError}
                month={data.filters.month}
                monthLabel={monthLabel}
                loadMonthTransactions={data.listMonthTransactions}
                onCreateCategory={createCategory}
                onRenameCategory={renameCategory}
                onDeleteCategory={deleteCategory}
                onArchiveCategory={archiveCategory}
                onUnarchiveCategory={unarchiveCategory}
              />
            ) : null}

            {section === "rules" ? (
              <RulesBudgetsPage
                rules={data.rules}
                categories={data.categories}
                assignableCategories={data.assignableCategories}
                budgets={data.budgets}
                summary={data.summary}
                onToggleRule={toggleRule}
                onUpdateRule={updateRule}
                onDeleteRule={deleteRule}
                onCreateBudget={createBudget}
                onUpdateBudget={updateBudget}
                onDeactivateBudget={deactivateBudget}
                onReactivateBudget={reactivateBudget}
                onRenameCategory={renameCategory}
              />
            ) : null}

            {section === "settings" ? (
              <SettingsPage
                connections={data.connections}
                accounts={data.accounts}
                onSyncConnection={syncConnection}
                onConnect={openConnect}
                onReconnect={openReconnect}
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
