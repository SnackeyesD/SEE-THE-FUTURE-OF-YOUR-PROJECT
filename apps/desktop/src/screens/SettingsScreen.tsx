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
} from "@see/ui";
import { useCallback, useEffect, useState } from "react";
import { ProvidersPanel } from "../components/ProvidersPanel";
import {
  agentTools,
  deleteAgentPermission,
  listAgentPermissions,
  setAgentPermission,
} from "../lib/ipc";
import { formatDateTime } from "../lib/format";
import type { LogLevel } from "../lib/logs";

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
            <ul className="mini-list">
              {permissions.events.slice(-12).reverse().map((event) => (
                <li key={event.id}>
                  <span>{formatDateTime(event.createdAt)}</span>
                  <strong>{event.tool}</strong>
                  <span>{event.decision}</span>
                  <span className="ui-muted">{event.actor}</span>
                </li>
              ))}
            </ul>
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
            <div className="facts">
              <div>
                <dt>État sidecar</dt>
                <dd>{status?.running ? "en marche" : "arrêté"}</dd>
              </div>
              <div>
                <dt>PID</dt>
                <dd>{status?.pid ?? "—"}</dd>
              </div>
              <div>
                <dt>Python</dt>
                <dd>{health?.python ?? "—"}</dd>
              </div>
              <div>
                <dt>Protocole</dt>
                <dd>{health?.protocolVersion ?? "—"}</dd>
              </div>
            </div>
            <div className="ui-actions">
              <Button variant="secondary" onClick={() => void onPing()} disabled={disabled}>
                Ping
              </Button>
              <Button variant="secondary" onClick={() => void onRestart()} disabled={disabled}>
                Redémarrer
              </Button>
            </div>
          </div>
          <div>
            <h3>Journal récent</h3>
            <ol className="log__list log__list--compact">
              {logs.length === 0 ? (
                <li className="log__empty">Aucun événement.</li>
              ) : (
                logs.slice(-12).map((entry) => (
                  <li key={entry.id} className={`log__line log__line--${entry.level}`}>
                    <span className="log__time">{entry.at}</span>
                    <span>{entry.message}</span>
                  </li>
                ))
              )}
            </ol>
          </div>
        </div>
        <InlineAlert tone="neutral">
          L'application reste utilisable hors ligne avec Ollama. Aucun cloud n'est requis pour
          créer un brief, simuler ou lire les résultats.
        </InlineAlert>
      </Card>
    </div>
  );
}
