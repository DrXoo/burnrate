import { Card } from "./ui/Card";

interface GettingStartedProps {
  onConnect: () => void;
}

export function GettingStarted({ onConnect }: GettingStartedProps) {
  return (
    <Card
      eyebrow="First run"
      title="Get started with BurnRate"
      subtitle="Connect a bank account to start seeing balances, spending, budgets, and runway. Here is the loop:"
      actions={
        <button type="button" className="button" onClick={onConnect}>
          Connect a bank
        </button>
      }
    >
      <div className="stack">
        <ol className="getting-started-steps">
          <li>
            <strong>Connect a bank account</strong> through Enable Banking using the button above.
          </li>
          <li>
            <strong>BurnRate imports</strong> your balances and transactions automatically and keeps them fresh.
          </li>
          <li>
            <strong>Categorize transactions</strong> and set monthly budgets per category.
          </li>
          <li>
            <strong>Watch money left, burn rate, and runway</strong> update live on this dashboard.
          </li>
        </ol>
        <p className="meta-copy">
          Note: this instance runs in Enable Banking restricted production mode, so only accounts that were
          pre-linked to the application will appear after you authorize.
        </p>
      </div>
    </Card>
  );
}
