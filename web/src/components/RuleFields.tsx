import type { MatchField, MatchOperator } from "../types";

interface RuleFieldsPatch {
  match_field?: MatchField;
  match_operator?: MatchOperator;
  match_value?: string;
}

interface RuleFieldsProps {
  matchField: MatchField;
  matchOperator: MatchOperator;
  matchValue: string;
  disabled?: boolean;
  onChange: (patch: RuleFieldsPatch) => void;
}

/** Shared match field/operator/value inputs used by rule creation and rule editing. */
export function RuleFields({ matchField, matchOperator, matchValue, disabled, onChange }: RuleFieldsProps) {
  return (
    <>
      <div className="dual-grid">
        <label>
          Match field
          <select
            value={matchField}
            disabled={disabled}
            onChange={(event) => onChange({ match_field: event.target.value as MatchField })}
          >
            <option value="description">Description</option>
            <option value="merchant_name">Merchant name</option>
            <option value="counterparty_name">Counterparty name</option>
          </select>
        </label>
        <label>
          Match type
          <select
            value={matchOperator}
            disabled={disabled}
            onChange={(event) => onChange({ match_operator: event.target.value as MatchOperator })}
          >
            <option value="contains">Contains</option>
            <option value="equals">Equals</option>
            <option value="starts_with">Starts with</option>
            <option value="ends_with">Ends with</option>
            <option value="regex">Regex</option>
          </select>
        </label>
      </div>
      <label>
        Match value
        <input
          value={matchValue}
          disabled={disabled}
          onChange={(event) => onChange({ match_value: event.target.value })}
          placeholder="Text or regex pattern"
        />
      </label>
    </>
  );
}
