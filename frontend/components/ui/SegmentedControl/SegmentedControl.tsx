import styles from "./SegmentedControl.module.css";

export interface SegmentedOption {
  value: string;
  label: string;
}

export interface SegmentedControlProps {
  options: SegmentedOption[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

/**
 * design/design-system.md §3 SegmentedControl. 2-3 option tab switcher.
 * Active: --color-surface fill + --color-text-primary. Inactive:
 * transparent + --color-text-secondary. Control-level disabled dims all
 * options (opacity convention, docs/design-decisions.md §5).
 */
export function SegmentedControl({ options, value, onChange, disabled = false }: SegmentedControlProps) {
  return (
    <div className={styles.group} role="tablist" data-disabled={disabled || undefined}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="tab"
          aria-selected={option.value === value}
          disabled={disabled}
          className={styles.option}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
