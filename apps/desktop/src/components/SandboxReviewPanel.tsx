import type { SandboxAnalysis, SandboxAuditRecord } from "@see/protocol";
import {
  SandboxError,
  runSandboxScript,
  sha256Hex,
  type SandboxResult,
} from "@see/sandbox";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  InlineAlert,
  Table,
  TextareaField,
} from "@see/ui";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  analyzeSandboxCode,
  exportSandboxAudit,
  listSandboxAudit,
  recordSandboxAudit,
} from "../lib/ipc";
import { formatDateTime } from "../lib/format";

export interface SandboxProposal {
  callId: string;
  code: string;
  codeHash: string;
  purpose: string;
  analysis: SandboxAnalysis;
}

interface Props {
  projectId: string;
  proposal: SandboxProposal;
  input: Record<string, unknown>;
  onClose: () => void;
  onContinue: (message: string) => Promise<void>;
}

const PYTHON_KEYWORDS = new Set([
  "False",
  "None",
  "True",
  "and",
  "as",
  "assert",
  "async",
  "await",
  "break",
  "class",
  "continue",
  "def",
  "del",
  "elif",
  "else",
  "except",
  "finally",
  "for",
  "from",
  "global",
  "if",
  "import",
  "in",
  "is",
  "lambda",
  "nonlocal",
  "not",
  "or",
  "pass",
  "raise",
  "return",
  "try",
  "while",
  "with",
  "yield",
]);

const PYTHON_BUILTINS = new Set([
  "abs",
  "all",
  "any",
  "bool",
  "dict",
  "enumerate",
  "float",
  "format",
  "int",
  "len",
  "list",
  "max",
  "min",
  "range",
  "round",
  "set",
  "sorted",
  "str",
  "sum",
  "tuple",
  "zip",
]);

const TOKEN_PATTERN = /(#.*$)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|\b(\d+(?:\.\d+)?)\b|\b([A-Za-z_]\w*)\b/g;

function highlightLine(line: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let cursor = 0;
  let index = 0;
  for (const match of line.matchAll(TOKEN_PATTERN)) {
    const start = match.index ?? 0;
    if (start > cursor) nodes.push(line.slice(cursor, start));
    const [token, comment, text, number, word] = match;
    if (comment) {
      nodes.push(
        <span className="sandbox-code__comment" key={index++}>
          {token}
        </span>,
      );
    } else if (text) {
      nodes.push(
        <span className="sandbox-code__string" key={index++}>
          {token}
        </span>,
      );
    } else if (number) {
      nodes.push(
        <span className="sandbox-code__number" key={index++}>
          {token}
        </span>,
      );
    } else if (word) {
      if (PYTHON_KEYWORDS.has(word)) {
        nodes.push(
          <span className="sandbox-code__keyword" key={index++}>
            {token}
          </span>,
        );
      } else if (PYTHON_BUILTINS.has(word)) {
        nodes.push(
          <span className="sandbox-code__builtin" key={index++}>
            {token}
          </span>,
        );
      } else {
        nodes.push(token);
      }
    }
    cursor = start + token.length;
  }
  if (cursor < line.length) nodes.push(line.slice(cursor));
  return nodes;
}

function CodeBlock({ code }: { code: string }) {
  return (
    <div className="sandbox-code" aria-label="Code Python proposé">
      {code.split("\n").map((line, index) => (
        <div className="sandbox-code__line" key={index}>
          <span className="sandbox-code__gutter">{index + 1}</span>
          <code>{line ? highlightLine(line) : "\u00a0"}</code>
        </div>
      ))}
    </div>
  );
}

function Sparkline({ label, x, y }: { label: string; x: number[]; y: number[] }) {
  if (x.length < 2 || y.length < 2) return null;
  const width = 260;
  const height = 84;
  const minX = Math.min(...x);
  const maxX = Math.max(...x);
  const minY = Math.min(...y);
  const maxY = Math.max(...y);
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;
  const points = x
    .map((value, index) => {
      const px = ((value - minX) / spanX) * (width - 16) + 8;
      const py = height - 8 - ((y[index] - minY) / spanY) * (height - 16);
      return `${px.toFixed(1)},${py.toFixed(1)}`;
    })
    .join(" ");
  return (
    <figure className="sandbox-series">
      <figcaption>{label}</figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
        <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
      <span className="ui-muted">
        {x.length} points, min {minY.toFixed(2)}, max {maxY.toFixed(2)}
      </span>
    </figure>
  );
}

function ResultView({ result }: { result: SandboxResult }) {
  return (
    <div className="sandbox-result">
      {result.summary ? <p className="sandbox-result__summary">{result.summary}</p> : null}
      {result.metrics?.length ? (
        <div className="sandbox-metrics">
          {result.metrics.map((metric) => (
            <div className="sandbox-metric" key={metric.label}>
              <span>{metric.label}</span>
              <strong>
                {metric.value.toLocaleString("fr-FR", { maximumFractionDigits: 3 })}
                {metric.unit ? ` ${metric.unit}` : ""}
              </strong>
            </div>
          ))}
        </div>
      ) : null}
      {result.series?.map((series) => (
        <Sparkline key={series.label} label={series.label} x={series.x} y={series.y} />
      ))}
      {result.tables?.map((table) => (
        <div className="sandbox-table" key={table.name}>
          <h4>{table.name}</h4>
          <table>
            <thead>
              <tr>
                {table.columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, index) => (
                <tr key={index}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex}>
                      {cell === null ? "—" : typeof cell === "boolean" ? String(cell) : cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

function statusTone(status: SandboxAuditRecord["status"]) {
  if (status === "succeeded") return "ok" as const;
  if (status === "rejected" || status === "failed") return "danger" as const;
  return "warn" as const;
}

export function SandboxReviewPanel({
  projectId,
  proposal,
  input,
  onClose,
  onContinue,
}: Props) {
  const [code, setCode] = useState(proposal.code);
  const [analysis, setAnalysis] = useState<SandboxAnalysis>(proposal.analysis);
  const [analyzing, setAnalyzing] = useState(false);
  const [running, setRunning] = useState(false);
  const [refusing, setRefusing] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<SandboxResult | null>(null);
  const [logs, setLogs] = useState("");
  const [durationMs, setDurationMs] = useState<number | null>(null);
  const [auditId, setAuditId] = useState<string | null>(null);
  const [continued, setContinued] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const sequence = useRef(0);

  useEffect(() => {
    const current = ++sequence.current;
    setAnalyzing(true);
    const timer = setTimeout(() => {
      void analyzeSandboxCode({ code })
        .then((response) => {
          if (current === sequence.current) setAnalysis(response.analysis);
        })
        .catch((reason) => {
          if (current === sequence.current) setError(String(reason));
        })
        .finally(() => {
          if (current === sequence.current) setAnalyzing(false);
        });
    }, 250);
    return () => clearTimeout(timer);
  }, [code]);

  useEffect(
    () => () => {
      abortRef.current?.abort();
    },
    [],
  );

  const canApprove =
    !running &&
    !refusing &&
    !analyzing &&
    analysis.ok &&
    analysis.codeHash.length === 64;

  const errors = useMemo(
    () => analysis.issues.filter((issue) => issue.severity === "error"),
    [analysis],
  );
  const warnings = useMemo(
    () => analysis.issues.filter((issue) => issue.severity === "warning"),
    [analysis],
  );

  const refuse = async () => {
    setRefusing(true);
    setError("");
    try {
      const fresh = await analyzeSandboxCode({ code });
      setAnalysis(fresh.analysis);
      const response = await recordSandboxAudit({
        projectId,
        code,
        codeHash: fresh.analysis.codeHash,
        purpose: proposal.purpose,
        decision: "rejected",
        status: "rejected",
      });
      setAuditId(response.record.id);
      onClose();
    } catch (reason) {
      setError(String(reason));
    } finally {
      setRefusing(false);
    }
  };

  const approve = async () => {
    setRunning(true);
    setError("");
    setResult(null);
    setLogs("");
    setAuditId(null);
    setContinued(false);
    const controller = new AbortController();
    abortRef.current = controller;
    let recordedStatus: SandboxAuditRecord["status"] | null = null;
    let hashForAudit = analysis.codeHash;
    try {
      const fresh = await analyzeSandboxCode({ code });
      setAnalysis(fresh.analysis);
      hashForAudit = fresh.analysis.codeHash;
      if (!fresh.analysis.ok) throw new Error("le script est refusé par l'analyse statique");
      const digest = await sha256Hex(code);
      if (digest !== fresh.analysis.codeHash) {
        throw new Error("l'empreinte du code ne correspond pas à l'analyse");
      }
      const output = await runSandboxScript({
        code,
        codeHash: fresh.analysis.codeHash,
        data: input,
        limits: {
          timeoutMs: fresh.analysis.limits.timeoutMs,
          workerStartTimeoutMs: fresh.analysis.limits.workerStartTimeoutMs,
          maxCodeBytes: fresh.analysis.limits.maxCodeBytes,
          maxInputBytes: fresh.analysis.limits.maxInputBytes,
          maxOutputBytes: fresh.analysis.limits.maxOutputBytes,
          maxLogBytes: fresh.analysis.limits.maxLogBytes,
        },
        signal: controller.signal,
      });
      setResult(output.result);
      setLogs(output.logs);
      setDurationMs(output.durationMs);
      recordedStatus = "succeeded";
      try {
        const response = await recordSandboxAudit({
          projectId,
          code,
          codeHash: fresh.analysis.codeHash,
          purpose: proposal.purpose,
          decision: "approved",
          status: "succeeded",
          result: output.result as unknown as Record<string, unknown>,
          durationMs: output.durationMs,
        });
        setAuditId(response.record.id);
      } catch (auditReason) {
        setError(`exécution réussie mais audit impossible : ${String(auditReason)}`);
      }
    } catch (reason) {
      const sandboxError = reason instanceof SandboxError ? reason : null;
      const status: SandboxAuditRecord["status"] =
        sandboxError?.code === "timeout"
          ? "timeout"
          : sandboxError?.code === "cancelled"
            ? "cancelled"
            : "failed";
      recordedStatus = status;
      setError(reason instanceof Error ? reason.message : String(reason));
      try {
        const response = await recordSandboxAudit({
          projectId,
          code,
          codeHash: hashForAudit,
          purpose: proposal.purpose,
          decision: "approved",
          status,
          error: (reason instanceof Error ? reason.message : String(reason)).slice(0, 2_000),
        });
        setAuditId(response.record.id);
      } catch (auditReason) {
        setError(`${String(reason)} — audit impossible : ${String(auditReason)}`);
      }
    } finally {
      abortRef.current = null;
      setRunning(false);
      if (recordedStatus === null) setError("exécution interrompue sans statut d'audit");
    }
  };

  const continueAgent = async () => {
    if (!result) return;
    setContinued(true);
    const payload = JSON.stringify(result).slice(0, 4_000);
    await onContinue(
      `Le script Python a été approuvé et exécuté dans la sandbox. Résultat structuré : ${payload}. Poursuis en tenant compte de ce résultat, sans inventer de chiffres.`,
    );
  };

  return (
    <div className="sandbox-overlay" role="dialog" aria-modal="true" aria-labelledby="sandbox-title">
      <section className="sandbox-panel">
        <header className="sandbox-panel__header">
          <div>
            <p className="ui-eyebrow">Revue humaine obligatoire</p>
            <h2 id="sandbox-title">Script Python proposé</h2>
            <p className="ui-muted">
              {proposal.purpose || "Aucune explication fournie."}{" "}
              <Badge tone="warn">explication IA non fiable</Badge>
            </p>
          </div>
          <Button variant="ghost" size="small" onClick={onClose} disabled={running}>
            Fermer
          </Button>
        </header>

        <div className="sandbox-panel__body">
          <div className="sandbox-panel__editor">
            <TextareaField
              label="Code (modifiable avant exécution)"
              value={code}
              onChange={setCode}
              rows={16}
              hint="Toute modification relance l'analyse statique et invalide l'approbation précédente."
            />
            <details className="details">
              <summary>Code coloré</summary>
              <CodeBlock code={code} />
            </details>
          </div>

          <aside className="sandbox-panel__analysis">
            <div className="sandbox-panel__status">
              <Badge tone={analysis.ok ? "ok" : "danger"}>
                {analysis.ok ? "Analyse validée" : "Analyse refusée"}
              </Badge>
              <Badge tone="neutral">hash {analysis.codeHash.slice(0, 12)}…</Badge>
              {analyzing ? <Badge tone="warn">analyse…</Badge> : null}
            </div>
            {errors.length > 0 ? (
              <InlineAlert tone="danger" title={`${errors.length} erreur(s) bloquante(s)`}>
                <ul className="mini-list">
                  {errors.map((issue, index) => (
                    <li key={`${issue.code}-${index}`}>
                      {issue.line ? `Ligne ${issue.line} : ` : ""}
                      {issue.message}
                    </li>
                  ))}
                </ul>
              </InlineAlert>
            ) : null}
            {warnings.length > 0 ? (
              <InlineAlert tone="warn" title="Avertissements">
                <ul className="mini-list">
                  {warnings.map((issue, index) => (
                    <li key={`${issue.code}-${index}`}>
                      {issue.line ? `Ligne ${issue.line} : ` : ""}
                      {issue.message}
                    </li>
                  ))}
                </ul>
              </InlineAlert>
            ) : null}
            <Table
              columns={[
                { key: "limit", header: "Limite" },
                { key: "value", header: "Valeur", mono: true },
              ]}
              rows={[
                { limit: "Timeout", value: `${analysis.limits.timeoutMs} ms` },
                { limit: "Mémoire", value: `${Math.round(analysis.limits.memoryBytes / 1_048_576)} Mo (best effort)` },
                { limit: "Sortie max", value: `${analysis.limits.maxOutputBytes.toLocaleString("fr-FR")} octets` },
              ]}
              rowKey={(row) => row.limit}
            />
            <p className="ui-muted">
              Imports autorisés : {analysis.allowedImports.join(", ")}.
            </p>
            <InlineAlert tone="neutral" title="Isolation">
              Python s'exécute dans un Web Worker Pyodide, sans accès au système, au réseau, à la
              base ni aux clés.
            </InlineAlert>
          </aside>
        </div>

        {error ? <InlineAlert tone="danger" title="Exécution impossible">{error}</InlineAlert> : null}

        {result ? (
          <div className="sandbox-panel__result">
            <h3>Résultat structuré</h3>
            <ResultView result={result} />
            <p className="ui-muted">
              Durée : {durationMs === null ? "—" : `${Math.round(durationMs)} ms`}
              {auditId ? ` — audit ${auditId.slice(0, 8)}` : ""}
            </p>
            {logs ? (
              <details className="details">
                <summary>Journaux d'exécution</summary>
                <pre className="sandbox-logs">{logs}</pre>
              </details>
            ) : null}
            <details className="details">
              <summary>JSON brut</summary>
              <pre className="sandbox-logs">{JSON.stringify(result, null, 2)}</pre>
            </details>
          </div>
        ) : null}

        <footer className="sandbox-panel__footer">
          <span className="ui-muted">
            {analysis.limits.timeoutMs} ms max · approbation valable pour ce hash uniquement
          </span>
          <div className="ui-actions">
            {running ? (
              <Button variant="secondary" onClick={() => abortRef.current?.abort()}>
                Annuler
              </Button>
            ) : null}
            {result && !continued ? (
              <Button variant="secondary" onClick={() => void continueAgent()} disabled={running}>
                Continuer avec l'agent
              </Button>
            ) : null}
            <Button
              variant="danger"
              onClick={() => void refuse()}
              disabled={running || refusing || analyzing}
            >
              Refuser
            </Button>
            <Button onClick={() => void approve()} disabled={!canApprove}>
              {running ? "Exécution…" : "Approuver et exécuter"}
            </Button>
          </div>
        </footer>
      </section>
    </div>
  );
}

export function SandboxAuditPanel({
  projectId,
  disabled,
  onLog,
}: {
  projectId: string;
  disabled: boolean;
  onLog: (level: "info" | "error" | "success", message: string) => void;
}) {
  const [records, setRecords] = useState<SandboxAuditRecord[]>([]);
  const [count, setCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const [exportPath, setExportPath] = useState("");

  const load = useCallback(async () => {
    if (disabled) return;
    setBusy(true);
    try {
      const response = await listSandboxAudit({ projectId });
      setRecords(response.records);
      setCount(response.count);
    } catch (reason) {
      onLog("error", `Audit sandbox: ${String(reason)}`);
    } finally {
      setBusy(false);
    }
  }, [disabled, onLog, projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  const exportAudit = async () => {
    setBusy(true);
    try {
      const response = await exportSandboxAudit({ projectId });
      setExportPath(response.path);
      onLog("success", `Audit sandbox exporté (${response.count}).`);
    } catch (reason) {
      onLog("error", `Export audit: ${String(reason)}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader
        eyebrow="Sandbox"
        title="Journal d'audit des scripts"
        description="Chaque décision et exécution est enregistrée localement avec le hash du code."
        action={
          <div className="ui-actions">
            <Button variant="ghost" size="small" onClick={() => void load()} disabled={busy || disabled}>
              Recharger
            </Button>
            <Button variant="secondary" size="small" onClick={() => void exportAudit()} disabled={busy || disabled}>
              Exporter
            </Button>
          </div>
        }
      />
      {records.length === 0 ? (
        <p className="ui-muted">Aucun script proposé ou exécuté pour ce projet.</p>
      ) : (
        <div className="sandbox-audit-list">
          {records.map((record) => (
            <details className="sandbox-audit" key={record.id}>
              <summary>
                <span>{formatDateTime(record.createdAt)}</span>
                <Badge tone={record.decision === "approved" ? "accent" : "neutral"}>
                  {record.decision}
                </Badge>
                <Badge tone={statusTone(record.status)}>{record.status}</Badge>
                <code>{record.codeHash.slice(0, 12)}…</code>
                <span className="ui-muted">
                  {record.durationMs === null ? "" : `${Math.round(record.durationMs)} ms`}
                </span>
              </summary>
              <p>{record.purpose || "Sans objet déclaré."}</p>
              {record.error ? <InlineAlert tone="danger" title="Échec de l'audit">{record.error}</InlineAlert> : null}
              <details className="details">
                <summary>Code audité</summary>
                <CodeBlock code={record.code} />
              </details>
              {record.result ? (
                <details className="details">
                  <summary>Résultat</summary>
                  <pre className="sandbox-logs">{JSON.stringify(record.result, null, 2)}</pre>
                </details>
              ) : null}
            </details>
          ))}
        </div>
      )}
      <p className="ui-muted">
        {count} entrée(s) au total.{exportPath ? ` Export : ${exportPath}` : ""}
      </p>
    </Card>
  );
}
