import type {
  AgentPendingPermission,
  AgentSession,
  AgentTurnParams,
  HealthResult,
  Project,
  ProjectDataResult,
  RoleName,
  Scenario,
  SidecarStatus,
} from "@see/protocol";
import { PROTOCOL_VERSION } from "@see/protocol";
import { Badge, Button, InlineAlert } from "@see/ui";
import { useCallback, useEffect, useState } from "react";
import { BriefScreen } from "./screens/BriefScreen";
import { HypothesesScreen } from "./screens/HypothesesScreen";
import { InterviewScreen } from "./screens/InterviewScreen";
import { ProjectsScreen } from "./screens/ProjectsScreen";
import { ResultsScreen } from "./screens/ResultsScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { SimulationScreen } from "./screens/SimulationScreen";
import {
  agentState,
  agentTurn,
  createProject,
  deleteAgentPermission,
  getProjectData,
  getSidecarHealth,
  getSidecarStatus,
  ipcAvailable,
  listAgentPermissions,
  listProjects,
  listRoles,
  onSimulationProgress,
  pingSidecar,
  restartSidecar,
  saveProjectBrief,
  saveProjectScenario,
  setAgentPermission,
  simulateProject,
} from "./lib/ipc";
import type { LogEntry, LogLevel } from "./lib/logs";

type View =
  | "projects"
  | "interview"
  | "brief"
  | "hypotheses"
  | "simulation"
  | "results"
  | "settings";

const NAV: Array<{ id: View; fr: string; en: string }> = [
  { id: "projects", fr: "Projets", en: "Projects" },
  { id: "interview", fr: "Entretien", en: "Interview" },
  { id: "brief", fr: "Brief", en: "Brief" },
  { id: "hypotheses", fr: "Hypothèses", en: "Assumptions" },
  { id: "simulation", fr: "Simulation", en: "Simulation" },
  { id: "results", fr: "Résultats", en: "Results" },
  { id: "settings", fr: "Réglages", en: "Settings" },
];

let nextLogId = 1;

function timestamp(): string {
  return new Date().toLocaleTimeString("fr-FR", { hour12: false });
}

function humanize(reason: unknown): string {
  const text = reason instanceof Error ? reason.message : String(reason);
  return text.replace(/^Error:\s*/i, "");
}

function suggestedView(data: ProjectDataResult, session: AgentSession | null): View {
  if (data.run) return "results";
  if (data.scenario) return "simulation";
  if (data.brief?.status === "validated") return "hypotheses";
  if (data.brief) return "brief";
  if (session && session.thread.length > 0) return "interview";
  return "interview";
}

export function App() {
  const [status, setStatus] = useState<SidecarStatus | null>(null);
  const [health, setHealth] = useState<HealthResult | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [data, setData] = useState<ProjectDataResult | null>(null);
  const [session, setSession] = useState<AgentSession | null>(null);
  const [roles, setRoles] = useState<RoleName[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [view, setView] = useState<View>("projects");
  const [pending, setPending] = useState<AgentPendingPermission[]>([]);
  const [progress, setProgress] = useState<number | null>(null);
  const [narration, setNarration] = useState("");
  const [narrationBusy, setNarrationBusy] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [online, setOnline] = useState(() => navigator.onLine);
  const [locale, setLocale] = useState<"fr" | "en">(() =>
    localStorage.getItem("seefuture.locale") === "en" ? "en" : "fr",
  );

  const pushLog = useCallback((level: LogLevel, message: string) => {
    setLogs((current) => [
      ...current.slice(-199),
      { id: nextLogId++, at: timestamp(), level, message },
    ]);
  }, []);

  const refreshStatus = useCallback(async () => {
    const nextStatus = await getSidecarStatus();
    setStatus(nextStatus);
    if (nextStatus.running) {
      setHealth(await getSidecarHealth());
    } else {
      setHealth(null);
    }
    return nextStatus;
  }, []);

  const refreshWorkspace = useCallback(async (projectId: string) => {
    const [nextData, nextSession, nextRoles] = await Promise.all([
      getProjectData({ projectId }),
      agentState({ projectId }),
      listRoles(projectId),
    ]);
    setData(nextData);
    setSession(nextSession.session);
    setRoles(nextRoles.assignments.map((assignment) => assignment.role as RoleName));
    return { data: nextData, session: nextSession.session, roles: nextRoles };
  }, []);

  const openProject = useCallback(
    async (project: Project) => {
      setActiveProject(project);
      localStorage.setItem("seefuture.project", project.id);
      setBusy(true);
      setError("");
      try {
        const loaded = await refreshWorkspace(project.id);
        setView(suggestedView(loaded.data, loaded.session));
      } catch (reason) {
        setError(humanize(reason));
        setView("projects");
      } finally {
        setBusy(false);
      }
    },
    [refreshWorkspace],
  );

  const loadProjects = useCallback(async () => {
    const result = await listProjects();
    setProjects(result.projects);
    return result.projects;
  }, []);

  const bootstrap = useCallback(async () => {
    if (!ipcAvailable) {
      pushLog("error", "Mode navigateur : IPC Tauri indisponible.");
      setError("Ouvrez l'application Tauri pour accéder au stockage local et au sidecar.");
      return;
    }
    setBusy(true);
    try {
      const nextStatus = await refreshStatus();
      pushLog(
        nextStatus.running ? "success" : "error",
        nextStatus.running
          ? `Sidecar actif${nextStatus.pid ? ` (pid ${nextStatus.pid})` : ""}.`
          : nextStatus.error ?? "Sidecar arrêté.",
      );
      const loaded = await loadProjects();
      const remembered = localStorage.getItem("seefuture.project");
      const selected =
        loaded.find((project) => project.id === remembered) ?? loaded[0] ?? null;
      if (selected) {
        setActiveProject(selected);
        const workspace = await refreshWorkspace(selected.id);
        setView(suggestedView(workspace.data, workspace.session));
      }
    } catch (reason) {
      pushLog("error", `Initialisation: ${humanize(reason)}`);
      setError(humanize(reason));
    } finally {
      setBusy(false);
    }
  }, [loadProjects, pushLog, refreshStatus, refreshWorkspace]);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  useEffect(() => {
    if (!ipcAvailable) return;
    let disposed = false;
    let unlisten: (() => void) | undefined;
    void onSimulationProgress((value) => setProgress(value)).then((fn) => {
      if (disposed) {
        fn();
        return;
      }
      unlisten = fn;
    });
    return () => {
      disposed = true;
      unlisten?.();
    };
  }, []);

  useEffect(() => {
    setNarration("");
  }, [activeProject?.id, data?.run?.id]);

  useEffect(() => {
    localStorage.setItem("seefuture.locale", locale);
    document.documentElement.lang = locale;
  }, [locale]);

  const navigate = useCallback((next: View) => {
    setError("");
    setView(next);
  }, []);

  const handleCreateProject = useCallback(
    async (name: string, description: string) => {
      setBusy(true);
      setError("");
      try {
        const result = await createProject(name, description);
        pushLog("success", `Projet « ${result.project.name} » créé.`);
        await loadProjects();
        await openProject(result.project);
        return true;
      } catch (reason) {
        setError(humanize(reason));
        return false;
      } finally {
        setBusy(false);
      }
    },
    [loadProjects, openProject, pushLog],
  );

  const handleRefreshProjects = useCallback(async () => {
    setBusy(true);
    try {
      const loaded = await loadProjects();
      if (activeProject) {
        const current = loaded.find((project) => project.id === activeProject.id);
        if (current) setActiveProject(current);
      }
    } catch (reason) {
      setError(humanize(reason));
    } finally {
      setBusy(false);
    }
  }, [activeProject, loadProjects]);

  const runAgentTurn = useCallback(
    async (params: AgentTurnParams) => {
      if (!activeProject) return null;
      setBusy(true);
      setError("");
      try {
        const result = await agentTurn(params);
        setSession(result.session);
        setPending(result.pendingPermissions);
        await refreshWorkspace(activeProject.id);
        const failed = result.toolEvents.filter((event) => !event.ok);
        if (failed.length > 0) {
          pushLog(
            "error",
            `Outils en échec : ${failed.map((event) => event.tool).join(", ")}`,
          );
        }
        if (result.status === "permission_required") {
          pushLog("info", "Une permission est requise pour continuer.");
        } else if (result.status === "requires_review") {
          setError("Une action attend une revue humaine avant exécution.");
        } else if (result.status === "tool_error") {
          setError("Un outil a échoué. Consultez le détail dans le journal.");
        } else if (result.status === "permission_denied") {
          setError("L'action a été refusée. L'agent peut continuer sans elle.");
        } else if (result.status === "max_iterations") {
          setError("L'agent a atteint sa limite d'itérations. Reformulez la demande.");
        }
        return result;
      } catch (reason) {
        setError(humanize(reason));
        pushLog("error", humanize(reason));
        return null;
      } finally {
        setBusy(false);
      }
    },
    [activeProject, pushLog, refreshWorkspace],
  );

  const handleSend = useCallback(
    async (message: string) => {
      if (!activeProject) return;
      await runAgentTurn({ projectId: activeProject.id, message });
    },
    [activeProject, runAgentTurn],
  );

  const handleResume = useCallback(
    async (approval: {
      tool: string;
      callId: string;
      decision: "allow" | "deny" | "always";
    }) => {
      if (!activeProject) return;
      setError("");
      try {
        if (approval.decision === "always") {
          await setAgentPermission({
            projectId: activeProject.id,
            tool: approval.tool,
            scope: "project",
            decision: "allow",
          });
        }
        if (approval.decision === "deny") {
          await setAgentPermission({
            projectId: activeProject.id,
            tool: approval.tool,
            scope: "project",
            decision: "deny",
          });
        }
        await runAgentTurn({
          projectId: activeProject.id,
          approvals: [approval.callId],
        });
        await listAgentPermissions({ projectId: activeProject.id }).catch(() => undefined);
      } catch (reason) {
        setError(humanize(reason));
      } finally {
        if (approval.decision === "deny") {
          await deleteAgentPermission({
            projectId: activeProject.id,
            tool: approval.tool,
            scope: "project",
          }).catch(() => undefined);
        }
      }
    },
    [activeProject, runAgentTurn],
  );

  const handleSaveBrief = useCallback(
    async (content: Record<string, unknown>, briefStatus: "draft" | "validated") => {
      if (!activeProject) return;
      setBusy(true);
      setError("");
      try {
        await saveProjectBrief({
          projectId: activeProject.id,
          content,
          status: briefStatus,
        });
        await refreshWorkspace(activeProject.id);
        pushLog("success", briefStatus === "validated" ? "Brief validé." : "Brief enregistré.");
      } catch (reason) {
        setError(humanize(reason));
      } finally {
        setBusy(false);
      }
    },
    [activeProject, pushLog, refreshWorkspace],
  );

  const handleSaveScenario = useCallback(
    async (name: string, scenario: Scenario) => {
      if (!activeProject) return false;
      setBusy(true);
      setError("");
      try {
        await saveProjectScenario({
          projectId: activeProject.id,
          name,
          model: scenario.model ?? "retail_depot",
          scenario,
        });
        await refreshWorkspace(activeProject.id);
        pushLog("success", `Scénario « ${name} » enregistré.`);
        return true;
      } catch (reason) {
        setError(humanize(reason));
        return false;
      } finally {
        setBusy(false);
      }
    },
    [activeProject, pushLog, refreshWorkspace],
  );

  const handleSimulate = useCallback(
    async (config: { runs: number; seed: number; histogramBins: number }) => {
      if (!activeProject) return;
      setBusy(true);
      setError("");
      setProgress(0);
      try {
        const result = await simulateProject({
          projectId: activeProject.id,
          config,
          progress: true,
        });
        await refreshWorkspace(activeProject.id);
        setProgress(1);
        pushLog(
          "success",
          `Simulation terminée : ${result.result.runs} runs en ${Math.round(result.result.durationMs)} ms.`,
        );
        navigate("results");
      } catch (reason) {
        setError(humanize(reason));
        setProgress(null);
      } finally {
        setBusy(false);
      }
    },
    [activeProject, navigate, pushLog, refreshWorkspace],
  );

  const handleNarrate = useCallback(async () => {
    if (!activeProject) return;
    setNarrationBusy(true);
    setError("");
    try {
      const result = await agentTurn({
        projectId: activeProject.id,
        role: "narrator",
        message:
          "Rédige la narration des résultats pour un décideur non technique. Explique les chiffres marquants, les risques et les prochaines décisions. N'invente aucun nombre.",
      });
      setSession(result.session);
      setPending(result.pendingPermissions);
      await refreshWorkspace(activeProject.id);
      if (result.text.trim()) {
        setNarration(result.text.trim());
      } else {
        setError("L'agent n'a pas produit de narration.");
      }
    } catch (reason) {
      setError(humanize(reason));
    } finally {
      setNarrationBusy(false);
    }
  }, [activeProject, refreshWorkspace]);

  const handlePing = useCallback(async () => {
    try {
      const result = await pingSidecar("ui");
      pushLog("success", `pong reçu à ${result.timestamp}.`);
      await refreshStatus();
    } catch (reason) {
      pushLog("error", humanize(reason));
    }
  }, [pushLog, refreshStatus]);

  const handleRestart = useCallback(async () => {
    try {
      const nextStatus = await restartSidecar();
      setStatus(nextStatus);
      setHealth(null);
      pushLog("info", "Redémarrage du sidecar demandé.");
      await refreshStatus();
    } catch (reason) {
      pushLog("error", humanize(reason));
    }
  }, [pushLog, refreshStatus]);

  const navLabel = (id: View): string => {
    const item = NAV.find((entry) => entry.id === id);
    return item ? item[locale] : id;
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand__mark">SF</span>
          <div>
            <strong>See The Future</strong>
            <span>{activeProject ? activeProject.name : "Simulation de décisions"}</span>
          </div>
        </div>
        <div className="app-header__meta">
          <Badge tone={online ? "neutral" : "warn"}>{online ? "En ligne" : "Hors ligne"}</Badge>
          <Badge tone={status?.running ? "ok" : "danger"}>
            {ipcAvailable ? (status?.running ? "Sidecar actif" : "Sidecar arrêté") : "Navigateur"}
          </Badge>
          {activeProject ? <Badge>{activeProject.currency} · local-first</Badge> : null}
          <Badge tone="accent">protocole {PROTOCOL_VERSION}</Badge>
        </div>
      </header>

      <nav className="app-nav" aria-label="Parcours">
        {NAV.map((item) => (
          <button
            key={item.id}
            type="button"
            className={view === item.id ? "app-nav__item app-nav__item--active" : "app-nav__item"}
            onClick={() => navigate(item.id)}
          >
            {navLabel(item.id)}
          </button>
        ))}
      </nav>

      {!ipcAvailable ? (
        <InlineAlert tone="warn" title="Application desktop requise">
          Le mode navigateur permet de prévisualiser l'interface, mais le stockage et le sidecar ne
          sont disponibles que dans Tauri.
        </InlineAlert>
      ) : null}

      {error && view === "settings" ? <InlineAlert tone="danger">{error}</InlineAlert> : null}

      {view === "projects" || !activeProject ? (
        <ProjectsScreen
          projects={projects}
          activeProject={activeProject}
          busy={busy}
          error={error}
          onCreate={handleCreateProject}
          onOpen={(project) => void openProject(project)}
          onRefresh={() => void handleRefreshProjects()}
        />
      ) : null}

      {view === "interview" && activeProject ? (
        <InterviewScreen
          project={activeProject}
          session={session}
          pending={pending}
          roles={roles}
          busy={busy}
          error={error}
          onSend={handleSend}
          onResume={handleResume}
          onOpenSettings={() => navigate("settings")}
        />
      ) : null}

      {view === "brief" && activeProject ? (
        <BriefScreen
          project={activeProject}
          brief={data?.brief ?? null}
          busy={busy}
          error={error}
          onSave={handleSaveBrief}
          onNext={() => navigate("hypotheses")}
        />
      ) : null}

      {view === "hypotheses" && activeProject ? (
        <HypothesesScreen
          project={activeProject}
          brief={data?.brief ?? null}
          scenario={data?.scenario ?? null}
          busy={busy}
          error={error}
          onSave={handleSaveScenario}
          onNext={() => navigate("simulation")}
          onBack={() => navigate("brief")}
        />
      ) : null}

      {view === "simulation" && activeProject ? (
        <SimulationScreen
          project={activeProject}
          scenario={data?.scenario ?? null}
          run={data?.run ?? null}
          progress={progress}
          busy={busy}
          error={error}
          onRun={handleSimulate}
          onOpenResults={() => navigate("results")}
          onBack={() => navigate("hypotheses")}
        />
      ) : null}

      {view === "results" && activeProject ? (
        <ResultsScreen
          run={data?.run ?? null}
          narration={narration}
          narrationBusy={narrationBusy}
          error={error}
          onNarrate={handleNarrate}
          onBack={() => navigate("simulation")}
        />
      ) : null}

      {view === "settings" && activeProject ? (
        <SettingsScreen
          project={activeProject}
          disabled={!ipcAvailable}
          status={status}
          health={health}
          locale={locale}
          logs={logs}
          onLog={pushLog}
          onLocale={setLocale}
          onPing={handlePing}
          onRestart={handleRestart}
        />
      ) : null}

      <footer className="app-footer">
        <span>Local-first · BYOK · les chiffres viennent du moteur</span>
        <Button variant="ghost" size="small" onClick={() => void bootstrap()} disabled={busy}>
          Recharger l'application
        </Button>
      </footer>
    </div>
  );
}
