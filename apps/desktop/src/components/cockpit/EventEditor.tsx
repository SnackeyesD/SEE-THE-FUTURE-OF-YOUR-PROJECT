import type { DistributionSpec, ScenarioEvent } from "@see/protocol";
import { EVENT_CATALOG_BY_TYPE } from "@see/protocol";
import { Button, Field, InlineAlert, SelectField } from "@see/ui";
import { useMemo, useRef, useState } from "react";

import { useDialogFocus } from "../../hooks/useDialogFocus";

type Draft = {
  start: string;
  duration: string;
  probability: string;
  enabled: boolean;
  target: string;
  mode: "multiplicative" | "additive";
  magnitude: DistributionSpec;
};

function numeric(value: string): number {
  return Number(value.replace(",", "."));
}

function parseMagnitude(
  kind: DistributionSpec["kind"],
  magnitude: DistributionSpec,
): string | null {
  const positive = (value: number | undefined): boolean =>
    value !== undefined && Number.isFinite(value);
  if (kind === "triangular") {
    if (!positive(magnitude.low) || !positive(magnitude.mode) || !positive(magnitude.high)) {
      return "Renseignez minimum, mode et maximum.";
    }
    if (!(magnitude.low! <= magnitude.mode! && magnitude.mode! <= magnitude.high!)) {
      return "La triangulaire exige minimum ≤ mode ≤ maximum.";
    }
    if (magnitude.low === magnitude.high) {
      return "Minimum et maximum doivent différer.";
    }
    return null;
  }
  if (kind === "uniform") {
    if (!positive(magnitude.low) || !positive(magnitude.high)) {
      return "Renseignez minimum et maximum.";
    }
    if (magnitude.low! >= magnitude.high!) {
      return "Le minimum doit être strictement inférieur au maximum.";
    }
    return null;
  }
  if (kind === "normal") {
    if (!positive(magnitude.mean) || !positive(magnitude.std)) {
      return "Renseignez moyenne et écart-type.";
    }
    if (magnitude.std! <= 0) return "L'écart-type doit être strictement positif.";
    return null;
  }
  if (kind === "lognormal") {
    if (!positive(magnitude.mean) || !positive(magnitude.sigma)) {
      return "Renseignez moyenne et sigma.";
    }
    if (magnitude.sigma! <= 0) return "Sigma doit être strictement positif.";
    return null;
  }
  if (kind === "poisson") {
    if (!positive(magnitude.mean)) return "Renseignez la moyenne.";
    if (magnitude.mean! <= 0) return "La moyenne doit être strictement positive.";
    return null;
  }
  if (kind === "empirical") {
    if (!magnitude.values || magnitude.values.length === 0) {
      return "Saisissez au moins une valeur (séparées par des virgules).";
    }
    if (magnitude.weights && magnitude.weights.some((weight) => weight < 0)) {
      return "Les poids doivent être positifs.";
    }
    return null;
  }
  return null;
}

/** Une magnitude multiplicative doit rester strictement positive (règle moteur). */
function multiplicativeIssue(magnitude: DistributionSpec): string | null {
  if (magnitude.kind === "lognormal") return null;
  if (magnitude.kind === "uniform" || magnitude.kind === "triangular") {
    return magnitude.low !== undefined && magnitude.low > 0
      ? null
      : "Une intensité multiplicative doit avoir une borne basse strictement positive.";
  }
  if (magnitude.kind === "empirical") {
    return magnitude.values && magnitude.values.length > 0 && Math.min(...magnitude.values) > 0
      ? null
      : "Une intensité multiplicative doit rester strictement positive.";
  }
  return "Une loi normale ou de Poisson peut devenir négative : choisissez une triangulaire, une uniforme ou une lognormale.";
}

/**
 * Éditeur d'un événement : fenêtre, probabilité, cible et intensité.
 * L'aperçu d'intensité ne fait que relire les paramètres saisis — il ne
 * simule rien. Les erreurs de validation du moteur sont affichées telles
 * quelles via `error`.
 */
export function EventEditor({
  event,
  horizon,
  error,
  onApply,
  onClose,
}: {
  event: ScenarioEvent;
  horizon: number;
  error?: string;
  onApply: (patch: Partial<ScenarioEvent>) => Promise<boolean> | void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  useDialogFocus(ref, onClose);
  const entry = EVENT_CATALOG_BY_TYPE[event.type];
  const [draft, setDraft] = useState<Draft>({
    start: String(event.startMonth),
    duration: String(event.durationMonths),
    probability: String(Math.round((event.probability ?? 1) * 100)),
    enabled: event.enabled !== false,
    target: event.target,
    mode: event.mode ?? entry.mode,
    magnitude: { ...event.magnitude },
  });
  const [localError, setLocalError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const kind = draft.magnitude.kind;
  const windowPreview = useMemo(() => {
    const start = numeric(draft.start);
    const duration = numeric(draft.duration);
    if (!Number.isInteger(start) || !Number.isInteger(duration)) return null;
    return { start, duration, end: start + duration - 1 };
  }, [draft.duration, draft.start]);

  const patchMagnitude = (patch: Partial<DistributionSpec>): void => {
    setDraft((current) => ({ ...current, magnitude: { ...current.magnitude, ...patch } }));
  };

  const apply = async (): Promise<void> => {
    if (submitting) return;
    const start = numeric(draft.start);
    const duration = numeric(draft.duration);
    const probability = numeric(draft.probability);
    if (!Number.isInteger(start) || start < 1 || start > horizon) {
      setLocalError(`Le début doit être un mois entier entre 1 et ${horizon}.`);
      return;
    }
    if (!Number.isInteger(duration) || duration < 1) {
      setLocalError("La durée doit être un nombre entier de mois, au minimum 1.");
      return;
    }
    if (start + duration - 1 > horizon) {
      setLocalError(
        `La fenêtre se termine au mois ${start + duration - 1}, au-delà de l'horizon (${horizon}).`,
      );
      return;
    }
    if (!Number.isFinite(probability) || probability < 0 || probability > 100) {
      setLocalError("La probabilité doit être comprise entre 0 et 100 %.");
      return;
    }
    const magnitudeError = parseMagnitude(kind, draft.magnitude);
    if (magnitudeError) {
      setLocalError(magnitudeError);
      return;
    }
    if (draft.mode === "multiplicative") {
      const issue = multiplicativeIssue(draft.magnitude);
      if (issue) {
        setLocalError(issue);
        return;
      }
    }
    setLocalError("");
    setSubmitting(true);
    try {
      await onApply({
        startMonth: start,
        durationMonths: duration,
        probability: probability / 100,
        enabled: draft.enabled,
        target: draft.target,
        mode: draft.mode,
        magnitude: draft.magnitude,
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="cockpit-dialog-backdrop" onPointerDown={onClose}>
      <div
        ref={ref}
        className="cockpit-dialog cockpit-dialog--editor"
        role="dialog"
        aria-modal="true"
        aria-labelledby="event-editor-title"
        data-hotkeys-scope="true"
        onPointerDown={(pointerEvent) => pointerEvent.stopPropagation()}
      >
        <div className="cockpit-dialog__head">
          <div>
            <h2 id="event-editor-title">{entry.label}</h2>
            <p className="ui-muted">
              {entry.description} Cible : {entry.allowedTargets.find((item) => item.id === draft.target)?.label ?? draft.target} ·{" "}
              {draft.mode === "multiplicative" ? "multiplicatif" : "additif"}
            </p>
          </div>
          <Button variant="ghost" size="small" onClick={onClose}>
            Fermer
          </Button>
        </div>

        {localError ? (
          <InlineAlert tone="danger" title="Événement invalide">
            {localError}
          </InlineAlert>
        ) : null}
        {error ? (
          <InlineAlert tone="danger" title="Refusé par le moteur">
            {error}
          </InlineAlert>
        ) : null}

        <div className="ui-field-grid">
          <Field
            label="Mois de début"
            type="number"
            min={1}
            max={horizon}
            value={draft.start}
            onChange={(change) => setDraft((current) => ({ ...current, start: change.target.value }))}
            hint={`1 à ${horizon}`}
          />
          <Field
            label="Durée (mois)"
            type="number"
            min={1}
            max={horizon}
            value={draft.duration}
            onChange={(change) =>
              setDraft((current) => ({ ...current, duration: change.target.value }))
            }
            hint={
              windowPreview
                ? `Couvre les mois ${windowPreview.start} à ${windowPreview.end}`
                : undefined
            }
          />
          <Field
            label="Probabilité d'occurrence (%)"
            type="number"
            min={0}
            max={100}
            step={1}
            value={draft.probability}
            onChange={(change) =>
              setDraft((current) => ({ ...current, probability: change.target.value }))
            }
            hint="100 % = événement certain, tirage une fois par run"
          />
          <SelectField
            label="Cible"
            value={draft.target}
            onChange={(change) =>
              setDraft((current) => ({ ...current, target: change.target.value }))
            }
          >
            {entry.allowedTargets.map((target) => (
              <option key={target.id} value={target.id}>
                {target.label}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Mode"
            value={draft.mode}
            onChange={(change) =>
              setDraft((current) => ({
                ...current,
                mode: change.target.value === "additive" ? "additive" : "multiplicative",
              }))
            }
            hint={
              draft.mode === "multiplicative"
                ? "Multiplie la cible (ex. coût × 1,15)"
                : "Ajoute à la cible (ex. délai + 2 mois)"
            }
          >
            <option value="multiplicative">Multiplicatif</option>
            <option value="additive">Additif</option>
          </SelectField>
          <label className="ui-field ui-field--checkbox">
            <span>Activé</span>
            <input
              type="checkbox"
              checked={draft.enabled}
              onChange={(change) =>
                setDraft((current) => ({ ...current, enabled: change.target.checked }))
              }
            />
            <span className="ui-field__hint">
              Un événement désactivé reste visible sur la frise et n'est pas tiré.
            </span>
          </label>
        </div>

        <fieldset className="cockpit-editor__magnitude">
          <legend>Intensité — loi {kind}</legend>
          {kind === "triangular" ? (
            <div className="ui-field-grid">
              <Field
                label="Minimum"
                type="number"
                step="any"
                value={String(draft.magnitude.low ?? "")}
                onChange={(change) => patchMagnitude({ low: numeric(change.target.value) })}
              />
              <Field
                label="Mode"
                type="number"
                step="any"
                value={String(draft.magnitude.mode ?? "")}
                onChange={(change) => patchMagnitude({ mode: numeric(change.target.value) })}
              />
              <Field
                label="Maximum"
                type="number"
                step="any"
                value={String(draft.magnitude.high ?? "")}
                onChange={(change) => patchMagnitude({ high: numeric(change.target.value) })}
              />
            </div>
          ) : kind === "uniform" ? (
            <div className="ui-field-grid">
              <Field
                label="Minimum"
                type="number"
                step="any"
                value={String(draft.magnitude.low ?? "")}
                onChange={(change) => patchMagnitude({ low: numeric(change.target.value) })}
              />
              <Field
                label="Maximum"
                type="number"
                step="any"
                value={String(draft.magnitude.high ?? "")}
                onChange={(change) => patchMagnitude({ high: numeric(change.target.value) })}
              />
            </div>
          ) : kind === "normal" ? (
            <div className="ui-field-grid">
              <Field
                label="Moyenne"
                type="number"
                step="any"
                value={String(draft.magnitude.mean ?? "")}
                onChange={(change) => patchMagnitude({ mean: numeric(change.target.value) })}
              />
              <Field
                label="Écart-type"
                type="number"
                step="any"
                value={String(draft.magnitude.std ?? "")}
                onChange={(change) => patchMagnitude({ std: numeric(change.target.value) })}
              />
            </div>
          ) : kind === "lognormal" ? (
            <div className="ui-field-grid">
              <Field
                label="Moyenne"
                type="number"
                step="any"
                value={String(draft.magnitude.mean ?? "")}
                onChange={(change) => patchMagnitude({ mean: numeric(change.target.value) })}
              />
              <Field
                label="Sigma"
                type="number"
                step="any"
                value={String(draft.magnitude.sigma ?? "")}
                onChange={(change) => patchMagnitude({ sigma: numeric(change.target.value) })}
              />
            </div>
          ) : kind === "poisson" ? (
            <Field
              label="Moyenne"
              type="number"
              step="any"
              value={String(draft.magnitude.mean ?? "")}
              onChange={(change) => patchMagnitude({ mean: numeric(change.target.value) })}
            />
          ) : (
            <Field
              label="Valeurs (séparées par des virgules)"
              value={(draft.magnitude.values ?? []).join(", ")}
              onChange={(change) =>
                patchMagnitude({
                  values: change.target.value
                    .split(",")
                    .map((item) => numeric(item.trim()))
                    .filter((value) => Number.isFinite(value)),
                })
              }
            />
          )}
          <p className="ui-muted">
            Aperçu de la fenêtre : mois {windowPreview?.start ?? "—"} à{" "}
            {windowPreview?.end ?? "—"} (durée inclusive). L'intensité est un paramètre, pas un
            résultat de simulation.
          </p>
        </fieldset>

        <div className="cockpit-dialog__actions">
          <Button variant="ghost" onClick={onClose}>
            Annuler
          </Button>
          <Button onClick={() => void apply()} disabled={submitting}>
            {submitting ? "Calcul en cours…" : "Appliquer et relancer"}
          </Button>
        </div>
      </div>
    </div>
  );
}
