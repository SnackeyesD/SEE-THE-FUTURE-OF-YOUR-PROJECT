import { cx } from "../cx";

export type StatTone = "neutral" | "ok" | "danger";

/**
 * Mesure — la valeur est TOUJOURS en mono à chiffres tabulaires
 * (charte R4). Label en uppercase, hint optionnel de contexte.
 */
export function Stat({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: StatTone;
}) {
  return (
    <div className={cx("ui-stat", tone !== "neutral" && `ui-stat--${tone}`)}>
      <span className="ui-stat__label">{label}</span>
      <strong className="ui-stat__value">{value}</strong>
      {hint ? <span className="ui-stat__hint">{hint}</span> : null}
    </div>
  );
}
