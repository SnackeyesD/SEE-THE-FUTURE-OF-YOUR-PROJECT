import type {
  Explanation,
  Provenance,
  ProvenanceInput,
  ProviderProfile,
  SimulationExplainResult,
} from "@see/protocol";
import { Badge, Button, InlineAlert } from "@see/ui";
import { useCallback, useEffect, useRef, useState } from "react";

import { useDialogFocus } from "../../hooks/useDialogFocus";
import { formatCurrency, formatNumber, formatPercent } from "../../lib/format";
import {
  explainMetric,
  getProvenance,
  listProfiles,
  listRoles,
} from "../../lib/ipc";

export interface ProvenanceTarget {
  metric: string;
  point: number | null;
}

export interface ProvenancePanelProps {
  projectId: string;
  runId: string;
  target: ProvenanceTarget;
  onClose: () => void;
}

const SOURCE_LABELS: Record<ProvenanceInput["source"], string> = {
  user: "utilisateur",
  benchmark: "benchmark",
  estimate: "estimation",
};

function formatValue(value: number, unit: string): string {
  if (unit === "%") return formatPercent(value, 1);
  if (unit === "mois") return `${formatNumber(value, 1)} mois`;
  if (unit === "unités") return `${formatNumber(value)} unités`;
  if (/^[A-Za-z]{3}$/.test(unit)) return formatCurrency(value, unit);
  return formatNumber(value, 2);
}

function formatInputNumber(value: number): string {
  return formatNumber(value, Number.isInteger(value) ? 0 : 2);
}

function humanize(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error);
  return text.replace(/^Error:\s*/i, "");
}

/** Valeur et fourchette telles que fournies par le sidecar, jamais recalculées. */
function ValueBlock({ provenance }: { provenance: Provenance }) {
  return (
    <dl className="provenance-values">
      <div>
        <dt>Valeur retenue</dt>
        <dd>{formatValue(provenance.value, provenance.unit)}</dd>
      </div>
      {provenance.range && provenance.range.length === 2 ? (
        <div>
          <dt>Fourchette P10–P90</dt>
          <dd>
            {formatValue(provenance.range[0], provenance.unit)} –{" "}
            {formatValue(provenance.range[1], provenance.unit)}
          </dd>
        </div>
      ) : null}
      <div>
        <dt>Graine</dt>
        <dd>{formatNumber(provenance.seed)}</dd>
      </div>
      <div>
        <dt>Runs</dt>
        <dd>{formatNumber(provenance.runs)}</dd>
      </div>
      <div>
        <dt>Moteur</dt>
        <dd>{provenance.engineVersion}</dd>
      </div>
    </dl>
  );
}

function InputTable({ inputs }: { inputs: ProvenanceInput[] }) {
  if (inputs.length === 0) {
    return <p className="ui-muted">Aucune hypothèse documentée pour ce calcul.</p>;
  }
  return (
    <div className="provenance-table">
      <table>
        <caption className="ui-visually-hidden">
          Hypothèses, sources et contribution à la variance
        </caption>
        <thead>
          <tr>
            <th scope="col">Hypothèse</th>
            <th scope="col">Valeur</th>
            <th scope="col">Plage tirée</th>
            <th scope="col">Source</th>
            <th scope="col">Contribution</th>
          </tr>
        </thead>
        <tbody>
          {inputs.map((input) => (
            <tr key={input.key}>
              <th scope="row">{input.label}</th>
              <td>{formatInputNumber(input.value)}</td>
              <td>
                {formatInputNumber(input.drawnRange[0])} –{" "}
                {formatInputNumber(input.drawnRange[1])}
              </td>
              <td>
                {SOURCE_LABELS[input.source]}
                {input.source === "benchmark" && input.benchmark ? (
                  <span className="ui-muted"> · {input.benchmark.label}</span>
                ) : null}
                {input.confidence !== null && input.confidence !== undefined ? (
                  <span className="ui-muted">
                    {" "}
                    · confiance {formatPercent(input.confidence, 0)}
                  </span>
                ) : null}
              </td>
              <td>
                {formatPercent(input.contribution, 1)}
                <span className="ui-muted">
                  {" "}
                  · corrélation {formatNumber(input.correlation, 2)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ExplanationBlock({
  explanation,
  source,
  reason,
  model,
  promptVersion,
  cached,
}: {
  explanation: Explanation;
  source: SimulationExplainResult["source"];
  reason: string | null;
  model: string | null;
  promptVersion: string;
  cached: boolean;
}) {
  return (
    <div className="provenance-explanation">
      <div className="provenance-explanation__head">
        {source === "llm" ? (
          <Badge tone="ok">généré à partir des données ci-dessus</Badge>
        ) : (
          <Badge tone="neutral">repli déterministe</Badge>
        )}
        {source === "llm" && cached ? <Badge tone="neutral">en cache</Badge> : null}
        {reason ? <span className="ui-muted">motif : {reason}</span> : null}
        <span className="ui-muted">
          {model ? `${model} · ` : ""}
          invite {promptVersion}
        </span>
      </div>
      <p>{explanation.summary}</p>
      {explanation.points.length > 0 ? (
        <ul>
          {explanation.points.map((point) => (
            <li key={point.text}>{point.text}</li>
          ))}
        </ul>
      ) : null}
      {explanation.caveats.length > 0 ? (
        <details>
          <summary>Limites à garder en tête</summary>
          <ul>
            {explanation.caveats.map((caveat) => (
              <li key={caveat}>{caveat}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

/**
 * Panneau « D'où vient ce chiffre ? ».
 *
 * Il affiche uniquement le payload de provenance produit par le sidecar et
 * les explications qu'il renvoie. L'explication IA reste optionnelle et
 * n'apparaît que si un fournisseur est configuré pour le rôle Narrateur ;
 * le repli déterministe reste disponible hors ligne.
 */
export function ProvenancePanel({
  projectId,
  runId,
  target,
  onClose,
}: ProvenancePanelProps) {
  const ref = useRef<HTMLDivElement | null>(null);
  useDialogFocus(ref, onClose);

  const [provenance, setProvenance] = useState<Provenance | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [explanation, setExplanation] = useState<SimulationExplainResult | null>(null);
  const [explainError, setExplainError] = useState<string | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [narrator, setNarrator] = useState<{
    profile: ProviderProfile;
    model: string;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    setProvenance(null);
    setLoadError(null);
    setExplanation(null);
    setExplainError(null);
    getProvenance({ runId, metric: target.metric, point: target.point })
      .then((result) => {
        if (!cancelled) setProvenance(result.provenance);
      })
      .catch((error: unknown) => {
        if (!cancelled) setLoadError(humanize(error));
      });
    return () => {
      cancelled = true;
    };
  }, [runId, target.metric, target.point]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([listProfiles(projectId), listRoles(projectId)])
      .then(([profiles, roles]) => {
        if (cancelled) return;
        const assignment = roles.assignments.find((item) => item.role === "narrator");
        if (!assignment) return;
        const profile = profiles.profiles.find(
          (item) => item.id === assignment.providerProfileId,
        );
        if (profile) setNarrator({ profile, model: assignment.model });
      })
      .catch(() => {
        // Sans fournisseur configuré, le panneau reste utilisable : seul le
        // bouton d'explication IA est absent.
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const runExplain = useCallback(
    (useAi: boolean) => {
      setExplaining(true);
      setExplainError(null);
      explainMetric({
        projectId,
        runId,
        metric: target.metric,
        point: target.point,
        ...(useAi && narrator
          ? { profile: narrator.profile, model: narrator.model }
          : {}),
      })
        .then((result) => setExplanation(result))
        .catch((error: unknown) => setExplainError(humanize(error)))
        .finally(() => setExplaining(false));
    },
    [narrator, projectId, runId, target.metric, target.point],
  );

  return (
    <div className="cockpit-dialog-backdrop" onPointerDown={onClose}>
      <div
        ref={ref}
        className="cockpit-dialog provenance-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="provenance-title"
        data-hotkeys-scope="true"
        onPointerDown={(event) => event.stopPropagation()}
      >
        <div className="cockpit-dialog__head">
          <div>
            <h2 id="provenance-title">D'où vient ce chiffre ?</h2>
            <p className="ui-muted">
              {target.point === null
                ? "Indicateur agrégé sur l'horizon"
                : `Point du mois ${target.point}`}{" "}
              · {target.metric}
            </p>
          </div>
          <Button variant="ghost" size="small" onClick={onClose}>
            Fermer
          </Button>
        </div>

        {loadError ? (
          <InlineAlert tone="danger" title="Provenance indisponible">
            {loadError}
          </InlineAlert>
        ) : provenance === null ? (
          <p className="ui-muted">Chargement de la provenance…</p>
        ) : (
          <>
            <p>{provenance.definition}</p>
            <p className="ui-muted">Formule : {provenance.formula}</p>
            <ValueBlock provenance={provenance} />
            <InputTable inputs={provenance.inputs} />
            {provenance.caveats.length > 0 ? (
              <details>
                <summary>Limites de ce calcul</summary>
                <ul>
                  {provenance.caveats.map((caveat) => (
                    <li key={caveat}>{caveat}</li>
                  ))}
                </ul>
              </details>
            ) : null}
            <p className="ui-muted">
              Empreinte du scénario : <code>{provenance.scenariosHash.slice(0, 12)}…</code>
            </p>
            <details>
              <summary>Données exactes transmises au fournisseur</summary>
              <pre className="provenance-payload">
                {JSON.stringify(provenance, null, 2)}
              </pre>
            </details>

            <section className="provenance-actions" aria-label="Explication du chiffre">
              <div className="ui-actions">
                <Button
                  variant="secondary"
                  size="small"
                  disabled={explaining}
                  onClick={() => runExplain(false)}
                >
                  Explication déterministe
                </Button>
                {narrator ? (
                  <Button
                    variant="primary"
                    size="small"
                    disabled={explaining}
                    onClick={() => runExplain(true)}
                  >
                    {explaining ? "Explication en cours…" : "Expliquer avec l'IA"}
                  </Button>
                ) : (
                  <span className="ui-muted">
                    Aucun fournisseur configuré pour le rôle Narrateur : l'explication IA
                    est désactivée.
                  </span>
                )}
              </div>
              {explainError ? (
                <InlineAlert tone="danger" title="Explication indisponible">
                  {explainError}
                </InlineAlert>
              ) : null}
              {explanation ? (
                <ExplanationBlock
                  explanation={explanation.explanation}
                  source={explanation.source}
                  reason={explanation.reason ?? null}
                  model={explanation.model ?? null}
                  promptVersion={explanation.promptVersion}
                  cached={explanation.cached}
                />
              ) : null}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
