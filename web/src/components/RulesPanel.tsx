import type { Rule, RuleUpdateDraft } from "../types";
import { Card } from "./ui/Card";
import { RuleCard } from "./RuleCard";

interface RulesPanelProps {
  rules: Rule[];
  onToggleRule: (ruleId: string, active: boolean) => Promise<void>;
  onUpdateRule: (ruleId: string, draft: RuleUpdateDraft) => Promise<void>;
  onDeleteRule: (ruleId: string) => Promise<void>;
}

export function RulesPanel({ rules, onToggleRule, onUpdateRule, onDeleteRule }: RulesPanelProps) {
  return (
    <Card title="Saved rules" subtitle="Text-based rules that auto-categorize matching transactions.">
      <div className="stack">
        {rules.length === 0 ? (
          <div className="empty-state">
            No saved rules yet. Categorize a transaction and save one from the transaction table.
          </div>
        ) : (
          rules.map((rule) => (
            <RuleCard
              key={rule.rule_id}
              rule={rule}
              onToggleRule={onToggleRule}
              onUpdateRule={onUpdateRule}
              onDeleteRule={onDeleteRule}
            />
          ))
        )}
      </div>
    </Card>
  );
}
