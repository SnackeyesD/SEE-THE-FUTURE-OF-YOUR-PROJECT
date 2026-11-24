import type {
  AgentPermissionListResult,
  AgentPermissionMode,
  AgentToolsResult,
  HealthResult,
  Project,
  SidecarStatus,
} from "@see/protocol";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  InlineAlert,
  SelectField,
  Table,
} from "@see/ui";
import { useCallback, useEffect, useState } from "react";
import { BenchmarkPacksPanel } from "../components/BenchmarkPacksPanel";
import { ProvidersPanel } from "../components/ProvidersPanel";
import { SandboxAuditPanel } from "../components/SandboxReviewPanel";
import {
  agentTools,
  deleteAgentPermission,
  listAgentPermissions,
  setAgentPermission,
} from "../lib/ipc";
import {
  clearCrashEntries,
  isCrashLogEnabled,
  readCrashEntries,
  setCrashLogEnabled,
} from "../lib/crashlog";
import { buildDiagnostic, diagnosticFilename } from "../lib/diagnostic";
import { downloadText } from "../lib/download";
import { formatDateTime } from "../lib/format";
import type { LogLevel } from "../lib/logs";
import { APP_VERSION } from "../lib/version";

interface Props {
  project: Project;
  disabled: boolean;
  status: SidecarStatus | null;
  health: HealthResult | null;
  locale: "fr" | "en";
  logs: Array<{ id: number; at: string; level: LogLevel; message: string }>;
  onLog: (level: LogLevel, message: string) => void;
  onLocale: (locale: "fr" | "en") => void;
  onPing: () => Promise<void>;
  onRestart: () => Promise<void>;
}

export function SettingsScreen({
  project,
  disabled,
  status,
  health,
  locale,
  logs,
  onLog,
  onLocale,
  onPing,
  onRestart,
}: Props) {
  const [permissions, setPermissions] = useState<AgentPermissionListResult | null>(null);
  const [tools, setTools] = useState<AgentToolsResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [crashLog, setCrashLog] = useState(isCrashLogEnabled);

  const loadPermissions = useCallback(async () => {
    if (disabled) return;
    try {
      const [permissionResult, toolResult] = await Promise.all([
        listAgentPermissions({ projectId: project.id }),
        agentTools(),
      ]);
      setPermissions(permissionResult);
      setTools(toolResult);
    } catch (reason) {
      onLog("error", `Permissions: ${String(reason)}`);
    }
  }, [disabled, onLog, project.id]);

  useEffect(() => {
    void loadPermissions();
  }, [loadPermissions]);

  const defaultDecisionFor = (tool: string): AgentPermissionMode => {
    const value = permissions?.defaults?.[tool];
    return value === "allow" || value === "ask" || value === "deny" ? value : "ask";
  };

  const decisionFor = (tool: string): AgentPermissionMode => {
    const override = permissions?.permissions.find(
      (item) => item.tool === tool && item.scope === "project",
    );
    return override?.decision ?? defaultDecisionFor(tool);
  };

  const changeDecision = async (tool: string, decision: AgentPermissionMode) => {
    setBusy(true);
    try {
      const result = await setAgentPermission({
        projectId: project.id,
        tool,
        scope: "project",
        decision,
      });
      setPermissions(result);
      onLog("success", `Permission ${tool} : ${decision}.`);
    } catch (reason) {
      onLog("error", `Permission ${tool}: ${String(reason)}`);
    } finally {
      setBusy(false);
    }
  };

  const resetDecision = async (tool: string) => {
    setBusy(true);
    try {
      const result = await deleteAgentPermission({
        projectId: project.id,
        tool,
        scope: "project",
      });
      setPermissions(result);
    } catch (reason) {
      onLog("error", `Réinitialisation ${tool}: ${String(reason)}`);
    } finally {
      setBusy(false);
    }
  };

  const exportDiagnostic = () => {
    const content = buildDiagnostic({
      appVersion: APP_VERSION,
      locale,
      userAgent: navigator.userAgent,
      status,
      health,
      logs,
      crashes: readCrashEntries(),
      projectNames: [project.name],
    });
    if (
      !downloadText(
        diagnosticFilename(),
        content,
        "application/json;charset=utf-8",
      )
    ) {
      onLog("error", "Le téléchargement du diagnostic n'est pas disponible ici.");
      return;
    }
    onLog("success", "Diagnostic local exporté (sans projet ni clé).");
  };

  const toggleCrashLog = (enabled: boolean) => {
    if (!setCrashLogEnabled(enabled)) {
      onLog("error", "La préférence n'a pas pu être enregistrée.");
      return;
    }
    setCrashLog(enabled);
    if (enabled) {
      onLog("info", "Journal local des erreurs activé : aucun envoi réseau.");
    } else {
      clearCrashEntries();
      onLog("info", "Journal local des erreurs désactivé et effacé.");
    }
  };

  return (
    <div className="screen">
      <div className="screen__heading">
        <div>
          <p className="ui-eyebrow">Réglages</p>
          <h1>Fournisseurs, permissions, diagnostic</h1>
          <p className="ui-muted">
            Les clés restent dans le trousseau. Les permissions sont appliquées côté agent.
          </p>
        </div>
        <div className="ui-actions">
          <Badge tone={status?.running ? "ok" : "danger"}>
            {status?.running ? "Sidecar actif" : "Sidecar arrêté"}
          </Badge>
          <SelectField
            label="Langue"
            value={locale}
            onChange={(event) => onLocale(event.target.value as "fr" | "en")}
          >
            <option value="fr">Français</option>
            <option value="en">English (préparé)</option>
          </SelectField>
        </div>
      </div>

      <ProvidersPanel disabled={disabled} onLog={onLog} initialProjectId={project.id} />

      <BenchmarkPacksPanel disabled={disabled} onLog={onLog} />

      <SandboxAuditPanel projectId={project.id} disabled={disabled} onLog={onLog} />

      <Card>
        <CardHeader
          eyebrow="Sécurité de l'agent"
          title="Permissions par outil"
          description="Un refus gagne toujours. Les scripts demandent toujours une revue humaine."
          action={
            <Button variant="ghost" size="small" onClick={() => void loadPermissions()} disabled={busy}>
              Recharger
            </Button>
          }
        />
        {!permissions ? (
          <p className="ui-muted">Chargement des permissions…</p>
        ) : (
          <div className="permission-table">
            {tools?.tools.map((tool) => {
              const alwaysAsk = permissions.alwaysAsk.includes(tool.name);
              const decision = decisionFor(tool.name);
              return (
                <div className="permission-row" key={tool.name}>
                  <div>
                    <strong>{tool.name}</strong>
                    <p className="ui-muted">{tool.description}</p>
                    <span className="ui-muted">
                      Défaut : {String(permissions.defaults[tool.name] ?? tool.defaultPermission)}
                      {alwaysAsk ? " · toujours demander" : ""}
                    </span>
                  </div>
                  <SelectField
                    label="Décision"
                    value={decision}
                    disabled={busy || alwaysAsk}
                    onChange={(event) =>
                      void changeDecision(tool.name, event.target.value as AgentPermissionMode)
                    }
                  >
                    <option value="allow">Autoriser</option>
                    <option value="ask">Demander</option>
                    <option value="deny">Refuser</option>
                  </SelectField>
                  <Button
                    variant="ghost"
                    size="small"
                    onClick={() => void resetDecision(tool.name)}
                    disabled={busy}
                  >
                    Défaut
                  </Button>
                </div>
              );
            })}
          </div>
        )}
        {permissions && permissions.events.length > 0 ? (
          <details className="details">
            <summary>Journal des décisions ({permissions.events.length})</summary>
            <Table
              columns={[
                { key: "createdAt", header: "Date", mono: true, render: (event) => formatDateTime(event.createdAt) },
                { key: "tool", header: "Outil" },
                { key: "decision", header: "Décision" },
                {
                  key: "actor",
                  header: "Source",
                  render: (event) => <span className="ui-muted">{event.actor}</span>,
                },
              ]}
              rows={permissions.events.slice(-12).reverse()}
              rowKey={(event) => event.id}
            />
          </details>
        ) : null}
      </Card>

      <Card>
        <CardHeader
          eyebrow="Diagnostic"
          title="Runtime local"
          description="Le shell Rust supervise le sidecar Python et son protocole JSON-RPC."
        />
        <div className="split">
          <div className="ui-stack">
            <Table
              columns={[
                { key: "measure", header: "Mesure" },
                { key: "value", header: "Valeur", mono: true },
              ]}
              rows={[
                { measure: "État sidecar", value: status?.running ? "en marche" : "arrêté" },
                { measure: "PID", value: status?.pid ?? "—" },
                { measure: "Python", value: health?.python ?? "—" },
                { measure: "Protocole", value: health?.protocolVersion ?? "—" },
              ]}
              rowKey={(row) => row.measure}
            />
            <div className="ui-actions">
              <Button variant="secondary" onClick={() => void onPing()} disabled={disabled}>
                Ping
              </Button>
              <Button variant="secondary" onClick={() => void onRestart()} disabled={disabled}>
                Redémarrer
              </Button>
              <Button variant="primary" onClick={exportDiagnostic}>
                Exporter le diagnostic
              </Button>
            </div>
            <label className="ui-field ui-field--checkbox">
              <input
                type="checkbox"
                checked={crashLog}
                onChange={(event) => toggleCrashLog(event.target.checked)}
              />
              <span>Journal local des erreurs (désactivé par défaut)</span>
            </label>
            <p className="ui-muted">
              {crashLog
                ? `${readCrashEntries().length} entrée(s) locale(s), nettoyées avant export. Aucun envoi réseau.`
                : "Aucun journal d'erreurs n'est conservé. Le diagnostic reste téléchargeable à la demande."}
            </p>
          </div>
          <div>
            <h3>Journal récent</h3>
            <Table
              columns={[
                { key: "at", header: "Heure", mono: true },
                {
                  key: "level",
                  header: "Niveau",
                  render: (entry) => (
                    <Badge tone={entry.level === "success" ? "ok" : entry.level === "error" ? "danger" : "neutral"}>
                      {entry.level}
                    </Badge>
                  ),
                },
                { key: "message", header: "Événement" },
              ]}
              rows={logs.slice(-12)}
              rowKey={(entry) => entry.id}
              empty="Aucun événement."
            />
          </div>
        </div>
        <InlineAlert tone="neutral" title="Fonctionne hors ligne">
          L'application reste utilisable avec Ollama. Aucun cloud n'est requis pour
          créer un brief, simuler ou lire les résultats.
        </InlineAlert>
      </Card>

      <Card>
        <CardHeader
          eyebrow="À propos"
          title="See The Future"
          description="Simulation Monte Carlo locale pour évaluer un projet avant de s'engager."
        />
        <Table
          columns={[
            { key: "label", header: "Élément" },
            { key: "value", header: "Valeur", mono: true },
          ]}
          rows={[
            { label: "Version de l'application", value: APP_VERSION },
            { label: "Protocole IPC", value: health?.protocolVersion ?? "non disponible" },
            { label: "Sidecar", value: health?.sidecarVersion ?? "non disponible" },
            { label: "Licence", value: "MIT" },
          ]}
          rowKey={(row) => row.label}
        />
        <InlineAlert tone="warn" title="Mentions de transparence">
          Les résultats sont des simulations basées sur vos hypothèses, pas une
          prévision garantie. Chaque dossier porte sa graine et sa version de
          moteur : deux runs ne se comparent que si ces valeurs sont identiques.
        </InlineAlert>
        <details className="details">
          <summary>Guide rapide (2 minutes)</summary>
          <ol className="ui-stack">
            <li>
              <strong>Projets</strong> → « Partir d'un projet d'exemple » :
              importez le dépôt de Brazzaville.
            </li>
            <li>
              Vérifiez les hypothèses marquées « estimation » dans
              <strong> Hypothèses</strong>.
            </li>
            <li>
              Lancez un calcul <strong>final</strong> dans <strong>Simulation</strong>.
              Un brouillon n'est jamais conservé.
            </li>
            <li>
              Lisez P10/P50/P90 et la probabilité de perte dans
              <strong> Résultats</strong>, puis exportez le dossier ou le PDF.
            </li>
            <li>
              Pour comparer deux runs, vérifiez qu'ils partagent la même graine
              et la même version de moteur.
            </li>
          </ol>
        </details>
        <details className="details">
          <summary>Confidentialité et conditions d'utilisation (provisoires)</summary>
          <div className="ui-stack">
            <p>
              <strong>Données locales.</strong> Projets, scénarios, runs, branches
              et diagnostics restent sur cette machine. Aucun compte ni
              synchronisation n'est requis.
            </p>
            <p>
              <strong>Fournisseur IA.</strong> Si vous configurez un fournisseur,
              seuls le brief, les hypothèses et le payload de provenance minimal
              lui sont envoyés pour produire une explication. La clé reste dans le
              trousseau du système.
            </p>
            <p>
              <strong>Télémétrie.</strong> Aucun envoi automatique. Le journal
              local d'erreurs est désactivé par défaut et l'export de diagnostic
              masque clés, chemins, courriels et noms de projets.
            </p>
            <p>
              <strong>Usage.</strong> L'outil aide à décider, il ne garantit ni
              profit, ni financement, ni conformité réglementaire. Vous restez
              responsable des hypothèses saisies et des décisions prises.
            </p>
          </div>
        </details>
      </Card>
    </div>
  );
}
