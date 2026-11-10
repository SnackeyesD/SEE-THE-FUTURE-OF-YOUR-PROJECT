import { cx } from "../cx";

/**
 * Barre de progression. `value` absent = indéterminée.
 * Respecte `prefers-reduced-motion` (animation désactivée en CSS).
 */
export function ProgressBar({
  value,
  label,
}: {
  value?: number;
  label: string;
}) {
  const clamped = value === undefined ? undefined : Math.max(0, Math.min(1, value));
  return (
    <div className="ui-progress">
      <div className="ui-progress__head">
        <span>{label}</span>
        <span>{clamped === undefined ? "…" : `${Math.round(clamped * 100)} %`}</span>
      </div>
      <div
        className={cx("ui-progress__track", clamped === undefined && "ui-progress__track--indeterminate")}
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={clamped === undefined ? undefined : Math.round(clamped * 100)}
      >
        <span style={clamped === undefined ? undefined : { width: `${clamped * 100}%` }} />
      </div>
    </div>
  );
}
