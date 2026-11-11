import { cx } from "../cx";

export type StatTone = "neutral" | "ok" | "danger";

/**
 * Mesure — la valeur est TOUJOURS en mono à chiffres tabulaires
 * (charte R4). Label en uppercase, unité optionnelle (rendue dans la
 * même mesure, adoucie), hint optionnel de contexte.
 */
export function Stat({
  label,
  value,
  unit,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: string;
  /** Unité de la mesure (ex. « FCFA », « unités/mois ») — jamais un chiffre. */
  unit?: string;
  hint?: string;
  tone?: StatTone;
}) {
  return (
    <div className={cx("ui-stat", tone !== "neutral" && `ui-stat--${tone}`)}>
      <span className="ui-stat__label">{label}</span>
      <strong className="ui-stat__value">
        {value}
        {unit ? <span className="ui-stat__unit">{unit}</span> : null}
      </strong>
      {hint ? <span className="ui-stat__hint">{hint}</span> : null}
    </div>
  );
}
