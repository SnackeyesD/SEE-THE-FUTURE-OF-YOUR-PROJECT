import type {
  AgentPendingPermission,
  AgentSession,
  AgentToolEvent,
  AgentTurnParams,
  HealthResult,
  Project,
  ProjectDataResult,
  RoleName,
  SandboxAnalysis,
  Scenario,
  SidecarStatus,
  TemplateSummary,
} from "@see/protocol";
import { PROTOCOL_VERSION } from "@see/protocol";
import { Badge, Button, InlineAlert } from "@see/ui";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

/* Thème : dark par défaut, bascule persistée (refont phase 06). */
type Theme = "dark" | "light";
const THEME_KEY = "sf-theme";
function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      const saved = window.localStorage.getItem(THEME_KEY);
      return saved === "light" ? "light" : "dark";
    } catch {
      return "dark";
    }
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      window.localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* stockage indisponible : la bascule reste effective pour la session */
    }
  }, [theme]);
  return [theme, setTheme] as const;
}
import {
  SandboxReviewPanel,
  type SandboxProposal,
} from "./components/SandboxReviewPanel";
import { GuidedTour } from "./components/onboarding/GuidedTour";
import { useViewHotkeys } from "./hooks/useViewHotkeys";
import { BriefScreen } from "./screens/BriefScreen";
import { BranchesScreen } from "./screens/BranchesScreen";
import { TokenBoard } from "./components/TokenBoard";
import { ComponentsShowcase } from "./components/ComponentsShowcase";
import { CockpitScreen } from "./screens/CockpitScreen";
import { HypothesesScreen } from "./screens/HypothesesScreen";
import { InterviewScreen } from "./screens/InterviewScreen";
import { ProjectsScreen } from "./screens/ProjectsScreen";
import { ResultsScreen } from "./screens/ResultsScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { SimulationScreen } from "./screens/SimulationScreen";
import {
  agentState,
  agentTurn,
  buildReport,
  createProject,
  createProjectFromTemplate,
  deleteAgentPermission,
  getProjectData,
  getScenario,
  getSidecarHealth,
  getSidecarStatus,
  ipcAvailable,
  listAgentPermissions,
  listProjects,
  listRoles,
  listTemplates,
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
  | "cockpit"
  | "branches"
  | "settings";

const VIEW_IDS: View[] = [
  "projects",
  "interview",
  "brief",
  "hypotheses",
  "simulation",
  "results",
  "cockpit",
  "branches",
  "settings",
];

const NAV: Array<{ id: View; fr: string; en: string }> = [
  { id: "projects", fr: "Projets", en: "Projects" },
  { id: "interview", fr: "Entretien", en: "Interview" },
  { id: "brief", fr: "Brief", en: "Brief" },
  { id: "hypotheses", fr: "Hypothèses", en: "Assumptions" },
  { id: "simulation", fr: "Simulation", en: "Simulation" },
  { id: "results", fr: "Résultats", en: "Results" },
  { id: "cockpit", fr: "Cockpit", en: "Cockpit" },
  { id: "branches", fr: "Branches", en: "Branches" },
  { id: "settings", fr: "Réglages", en: "Settings" },
];

let nextLogId = 1;

const DEMO_TEMPLATE_ID = "retail-depot-brazzaville";

function downloadText(filename: string, content: string): boolean {
  try {
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.rel = "noopener";
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    return true;
  } catch {
    return false;
  }
}

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

function sandboxProposalFromEvent(event: AgentToolEvent): SandboxProposal | null {
  if (event.tool !== "run_custom_script" || !event.requiresReview) return null;
  if (!event.result || typeof event.result !== "object") return null;
  const result = event.result as Record<string, unknown>;
  const analysis = result.analysis;
  if (
    typeof result.code !== "string" ||
    typeof result.codeHash !== "string" ||
    !analysis ||
    typeof analysis !== "object"
  ) {
    return null;
  }
  const parsed = analysis as SandboxAnalysis;
  if (
    typeof parsed.ok !== "boolean" ||
    !Array.isArray(parsed.issues) ||
    !Array.isArray(parsed.allowedImports) ||
    !parsed.limits
  ) {
    return null;
  }
  return {
    callId: event.callId,
    code: result.code,
    codeHash: result.codeHash,
    purpose: typeof result.purpose === "string" ? result.purpose : "",
    analysis: parsed,
  };
}

export function App() {
  const [theme, setTheme] = useTheme();
  const [status, setStatus] = useState<SidecarStatus | null>(null);
  const [health, setHealth] = useState<HealthResult | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [data, setData] = useState<ProjectDataResult | null>(null);
  /** Branche ouverte depuis l'écran Branches ; null = scénario courant du projet. */
  const [openedScenario, setOpenedScenario] = useState<
    NonNullable<ProjectDataResult["scenario"]> | null
  >(null);
  const [session, setSession] = useState<AgentSession | null>(null);
  const [roles, setRoles] = useState<RoleName[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [view, setView] = useState<View>("projects");
  const [pending, setPending] = useState<AgentPendingPermission[]>([]);
  const [progress, setProgress] = useState<number | null>(null);
  const [sandboxProposal, setSandboxProposal] = useState<SandboxProposal | null>(null);
  const [narration, setNarration] = useState("");
  const [narrationBusy, setNarrationBusy] = useState(false);
  const [reportBusy, setReportBusy] = useState(false);
  const cockpitDirty = useRef(false);
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

  const sandboxInput = useMemo<Record<string, unknown>>(
    () => ({
      project: activeProject
        ? {
            id: activeProject.id,
            name: activeProject.name,
            currency: activeProject.currency,
            description: activeProject.description,
          }
        : null,
      brief: data?.brief?.content ?? null,
      scenario: data?.scenario?.scenario ?? null,
      results: data?.run?.result ?? null,
    }),
    [activeProject, data],
  );

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
      setSandboxProposal(null);
      setOpenedScenario(null);
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

  const loadTemplates = useCallback(async () => {
    const result = await listTemplates();
    setTemplates(result.templates);
    return result.templates;
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
      try {
        await loadTemplates();
      } catch {
        /* les modèles sont optionnels : l'absence ne bloque pas le reste */
      }
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
  }, [loadProjects, loadTemplates, pushLog, refreshStatus, refreshWorkspace]);

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
    setSandboxProposal(null);
  }, [activeProject?.id]);

  useEffect(() => {
    localStorage.setItem("seefuture.locale", locale);
    document.documentElement.lang = locale;
  }, [locale]);

  const confirmDiscardCockpit = useCallback((): boolean => {
    if (!cockpitDirty.current) return true;
    try {
      return window.confirm(
        "Le scénario du cockpit contient des modifications non enregistrées. Quitter et les perdre ?",
      );
    } catch {
      // Environnement sans `confirm` (tests, webview restreinte).
      return true;
    }
  }, []);

  const navigate = useCallback(
    (next: View) => {
      setError("");
      if (next === "cockpit") setOpenedScenario(null);
      setView((current) => {
        if (current === "cockpit" && next !== "cockpit") {
          if (!confirmDiscardCockpit()) return current;
          cockpitDirty.current = false;
        }
        return next;
      });
    },
    [confirmDiscardCockpit],
  );

  const handleReload = useCallback(() => {
    if (view === "cockpit" && !confirmDiscardCockpit()) return;
    cockpitDirty.current = false;
    void bootstrap();
  }, [bootstrap, confirmDiscardCockpit, view]);

  useViewHotkeys({
    views: VIEW_IDS,
    onSelect: (id) => navigate(id as View),
    enabled: !sandboxProposal,
  });

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

  const handleCreateFromTemplate = useCallback(
    async (templateId: string) => {
      setBusy(true);
      setError("");
      try {
        const result = await createProjectFromTemplate(templateId);
        pushLog(
          "success",
          `Projet d'exemple « ${result.project.name} » importé (${result.seed}).`,
        );
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

  const handleExportReport = useCallback(async () => {
    if (!activeProject) return;
    setReportBusy(true);
    setError("");
    try {
      const report = await buildReport({
        projectId: activeProject.id,
        runId: data?.run?.id,
      });
      if (!downloadText(report.filename, report.content)) {
        setError("Le téléchargement du dossier n'est pas disponible dans cet environnement.");
        return;
      }
      pushLog("success", `Dossier exporté : ${report.filename}.`);
    } catch (reason) {
      setError(humanize(reason));
    } finally {
      setReportBusy(false);
    }
  }, [activeProject, data?.run?.id, pushLog]);

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
        const review = result.toolEvents
          .map(sandboxProposalFromEvent)
          .filter((item): item is SandboxProposal => item !== null)
          .at(-1);
        setSandboxProposal(review ?? null);
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
          if (!review) {
            setError("Une action attend une revue humaine avant exécution.");
          }
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

  const handleSandboxContinue = useCallback(
    async (message: string) => {
      setSandboxProposal(null);
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
        const saved = await saveProjectScenario({
          projectId: activeProject.id,
          name,
          model: scenario.model ?? "retail_depot",
          scenario,
          ...(openedScenario ? { scenarioId: openedScenario.id } : {}),
        });
        if (openedScenario) setOpenedScenario(saved.scenario);
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
    [activeProject, openedScenario, pushLog, refreshWorkspace],
  );

  const openBranchFromList = useCallback(
    async (scenarioId: string) => {
      if (!activeProject) return;
      setBusy(true);
      setError("");
      try {
        const result = await getScenario({
          projectId: activeProject.id,
          scenarioId,
        });
        setOpenedScenario(result.scenario);
        setView("cockpit");
      } catch (reason) {
        setError(humanize(reason));
      } finally {
        setBusy(false);
      }
    },
    [activeProject],
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
          // Le run persisté est celui que le cockpit recharge : il doit
          // contenir les distributions de tous les mois (final uniquement).
          config: { ...config, includeMonthlyHistograms: true },
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

  // Planche de contrôle des tokens (refont phase 02) — dev uniquement.
  if (new URLSearchParams(window.location.search).has("tokens")) {
    return <TokenBoard />;
  }

  // Vitrine des primitives (refont phase 03) — dev uniquement.
  if (new URLSearchParams(window.location.search).has("showcase")) {
    return <ComponentsShowcase />;
  }

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

      {activeProject?.metadata?.templateId === DEMO_TEMPLATE_ID ? (
        <GuidedTour
          projectId={activeProject.id}
          onNavigate={(next) => navigate(next as View)}
        />
      ) : null}

      {!ipcAvailable ? (
        <InlineAlert tone="warn" title="Application desktop requise">
          Le mode navigateur permet de prévisualiser l'interface, mais le stockage et le sidecar ne
          sont disponibles que dans Tauri.
        </InlineAlert>
      ) : null}

      {error && view === "settings" ? <InlineAlert tone="danger" title="Action impossible">{error}</InlineAlert> : null}

      {view === "projects" || !activeProject ? (
        <ProjectsScreen
          projects={projects}
          activeProject={activeProject}
          templates={templates}
          busy={busy}
          error={error}
          onCreate={handleCreateProject}
          onCreateFromTemplate={handleCreateFromTemplate}
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
          reportBusy={reportBusy}
          error={error}
          onNarrate={handleNarrate}
          onExportReport={handleExportReport}
          onBack={() => navigate("simulation")}
        />
      ) : null}

      {view === "cockpit" && activeProject ? (
        <CockpitScreen
          project={activeProject}
          scenario={openedScenario ?? data?.scenario ?? null}
          run={openedScenario ? null : data?.run ?? null}
          branchKey={openedScenario ? `branch:${openedScenario.id}` : null}
          onBack={() => navigate("results")}
          onOpenHypotheses={() => navigate("hypotheses")}
          onSaveScenario={handleSaveScenario}
          onDirtyChange={(dirty) => {
            cockpitDirty.current = dirty;
          }}
        />
      ) : null}

      {view === "branches" && activeProject ? (
        <BranchesScreen
          project={activeProject}
          activeScenarioId={openedScenario?.id ?? data?.scenario?.id ?? null}
          currency={activeProject.currency}
          onOpenBranch={openBranchFromList}
          onChanged={() => {
            void refreshWorkspace(activeProject.id).catch((reason) =>
              setError(humanize(reason)),
            );
          }}
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

      {sandboxProposal && activeProject ? (
        <SandboxReviewPanel
          projectId={activeProject.id}
          proposal={sandboxProposal}
          input={sandboxInput}
          onClose={() => setSandboxProposal(null)}
          onContinue={handleSandboxContinue}
        />
      ) : null}

      <footer className="app-footer">
        <span>Local-first · BYOK · les chiffres viennent du moteur</span>
        <div className="ui-actions">
          <Button
            variant="ghost"
            size="small"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? "Thème clair" : "Thème sombre"}
          </Button>
          <Button variant="ghost" size="small" onClick={handleReload} disabled={busy}>
            Recharger l'application
          </Button>
        </div>
      </footer>
    </div>
  );
}
