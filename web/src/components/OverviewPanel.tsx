import { Card } from "./ui/Card";

interface OverviewPanelProps {
  connections: number;
  accounts: number;
  uncategorizedCount: number;
  apiBase: string | null;
}

export function OverviewPanel({ connections, accounts, uncategorizedCount, apiBase }: OverviewPanelProps) {
  return (
    <Card
      title="Ledger overview"
      subtitle="Live backend data, current workflow surface, and the unknown queue count that still needs attention."
      actions={apiBase ? <span className="glass-pill">API {apiBase}</span> : null}
    >
      <div className="stats-grid">
        <article className="stat-card">
          <span className="stat-label">Connections</span>
          <strong className="stat-value">{connections}</strong>
        </article>
        <article className="stat-card">
          <span className="stat-label">Accounts</span>
          <strong className="stat-value">{accounts}</strong>
        </article>
        <article className="stat-card stat-card-warn">
          <span className="stat-label">Unknown queue</span>
          <strong className="stat-value">{uncategorizedCount}</strong>
        </article>
      </div>
    </Card>
  );
}
