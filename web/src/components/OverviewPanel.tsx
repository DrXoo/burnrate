import { formatMoney, formatMonthLabel, formatRunwayMonths, prettyLabel } from "../lib/format";
import type { BudgetUsage, SummaryDashboard } from "../types";
import { Card } from "./ui/Card";
import { StatusTag } from "./ui/StatusTag";

interface OverviewPanelProps {
  summary: SummaryDashboard | null;
  summaryLoading: boolean;
  summaryError: string | null;
  uncategorizedCount: number;
  apiBase: string | null;
  activeMonth: string;
}

function runwayTone(status: SummaryDashboard["runway_status"]): "default" | "good" | "warn" | "danger" {
  if (status === "critical") {
    return "danger";
  }
  if (status === "watch") {
    return "warn";
  }
  if (status === "stable") {
    return "good";
  }
  return "default";
}

function usageTone(status: BudgetUsage["status"]): "default" | "good" | "warn" | "danger" {
  if (status === "over") {
    return "danger";
  }
  if (status === "watch") {
    return "warn";
  }
  return "good";
}

function moneyTone(amount: string): string {
  return Number(amount) < 0 ? "stat-card-danger" : "";
}

export function OverviewPanel({
  summary,
  summaryLoading,
  summaryError,
  uncategorizedCount,
  apiBase,
  activeMonth,
}: OverviewPanelProps) {
  return (
    <Card
      title="BurnRate dashboard"
      subtitle="Live balances, monthly spending, budget pressure, and runway in one place."
      actions={
        <div className="dashboard-actions">
          <span className="glass-pill">{formatMonthLabel(activeMonth)}</span>
          {apiBase ? <span className="glass-pill">API {apiBase}</span> : null}
        </div>
      }
    >
      {summaryLoading && !summary ? (
        <div className="loading-stage summary-loading">
          <div className="loading-orb" />
          <p>Calculating the month view and budget pressure...</p>
        </div>
      ) : null}

      {summaryError && !summary ? <div className="error-banner">{summaryError}</div> : null}

      {summary ? (
        <div className="dashboard-stack">
          <div className="summary-grid">
            <article className="stat-card stat-card-highlight">
              <span className="stat-label">Current balance</span>
              <strong className="stat-value">
                {formatMoney(summary.current_balance_amount, summary.current_balance_currency)}
              </strong>
              <p className="meta-copy">Across accounts included in calculations.</p>
            </article>

            <article className="stat-card">
              <span className="stat-label">Monthly spending</span>
              <strong className="stat-value">
                {formatMoney(summary.monthly_spending_amount, summary.current_balance_currency)}
              </strong>
              <p className="meta-copy">
                {formatMoney(summary.average_daily_spend_amount, summary.current_balance_currency)} per day so far.
              </p>
            </article>

            <article className={`stat-card ${moneyTone(summary.money_left_amount)}`.trim()}>
              <span className="stat-label">Money left</span>
              <strong className="stat-value">
                {formatMoney(summary.money_left_amount, summary.current_balance_currency)}
              </strong>
              <p className="meta-copy">
                {formatMoney(summary.budgeted_spending_amount, summary.current_balance_currency)} of{" "}
                {formatMoney(summary.monthly_budget_amount, summary.current_balance_currency)} budgeted spend used.
              </p>
            </article>

            <article
              className={`stat-card ${summary.projected_overspend_amount !== "0.00" ? "stat-card-danger" : ""}`.trim()}
            >
              <span className="stat-label">Projected month end</span>
              <strong className="stat-value">
                {formatMoney(summary.projected_month_end_spend_amount, summary.current_balance_currency)}
              </strong>
              <p className="meta-copy">
                Based on {summary.days_elapsed} of {summary.days_in_month} days elapsed.
              </p>
            </article>

            <article className="stat-card">
              <span className="stat-label">Runway</span>
              <strong className="stat-value">{formatRunwayMonths(summary.runway_months_left, summary.runway_status)}</strong>
              <p className="meta-copy">
                {formatMoney(summary.runway_balance_amount, summary.runway_balance_currency)} reserved across{" "}
                {summary.runway_account_count} runway account(s).
              </p>
            </article>

            <article className={`stat-card ${uncategorizedCount > 0 ? "stat-card-warn" : ""}`.trim()}>
              <span className="stat-label">Unknown queue</span>
              <strong className="stat-value">{uncategorizedCount}</strong>
              <p className="meta-copy">
                {uncategorizedCount > 0
                  ? "Transactions still waiting for category cleanup this month."
                  : "All transactions categorized this month."}
              </p>
            </article>
          </div>

          <div className="dashboard-detail-grid">
            <section className="dashboard-block">
              <div className="row">
                <strong>Budget pulse</strong>
                <StatusTag tone={runwayTone(summary.runway_status)}>
                  {summary.projected_overspend_amount === "0.00"
                    ? "On plan"
                    : `${formatMoney(summary.projected_overspend_amount, summary.current_balance_currency)} overspend risk`}
                </StatusTag>
              </div>

              {summary.budget_usage.length > 0 ? (
                <div className="budget-radar">
                  {summary.budget_usage.map((budget) => {
                    const width = Math.min(100, Math.max(0, budget.utilization_percent));

                    return (
                      <article key={budget.category_id} className="budget-radar-item">
                        <div className="row">
                          <div>
                            <strong>{budget.category_name}</strong>
                            <p className="meta-copy">
                              {formatMoney(budget.spent_amount, budget.currency)} spent of{" "}
                              {formatMoney(budget.budget_amount, budget.currency)}
                            </p>
                          </div>
                          <StatusTag tone={usageTone(budget.status)}>
                            {budget.utilization_percent.toFixed(1)}%
                          </StatusTag>
                        </div>
                        <div className="progress-track">
                          <div
                            className={`progress-fill progress-${budget.status}`.trim()}
                            style={{ width: `${width}%` }}
                          />
                        </div>
                        <p className="meta-copy">
                          Remaining {formatMoney(budget.remaining_amount, budget.currency)}
                        </p>
                      </article>
                    );
                  })}
                </div>
              ) : (
                <div className="empty-state">No active monthly budgets for this month yet.</div>
              )}
            </section>

            <section className="dashboard-block">
              <div className="row">
                <strong>Runway context</strong>
                <StatusTag tone={runwayTone(summary.runway_status)}>{prettyLabel(summary.runway_status)}</StatusTag>
              </div>
              <p className="meta-copy">{summary.runway_message}</p>
              <div className="dashboard-context">
                <article className="mini-metric">
                  <span className="stat-label">{summary.runway_drain_label}</span>
                  <strong>{formatMoney(summary.runway_drain_amount, summary.runway_drain_currency)}</strong>
                </article>
                <article className="mini-metric">
                  <span className="stat-label">Runway reserve</span>
                  <strong>{formatMoney(summary.runway_balance_amount, summary.runway_balance_currency)}</strong>
                </article>
              </div>
              {summary.runway_accounts.length > 0 ? (
                <div className="account-chip-list">
                  {summary.runway_accounts.map((account) => (
                    <article key={account.account_id} className="account-chip">
                      <strong>{account.display_name}</strong>
                      <span>{formatMoney(account.balance_amount, account.balance_currency)}</span>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="empty-state">
                  No runway accounts selected yet. Use the Accounts section to add reserve accounts.
                </div>
              )}
            </section>
          </div>
        </div>
      ) : null}
    </Card>
  );
}
