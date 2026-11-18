import type {
  AgentPermissionDeleteParams,
  AgentPermissionDeleteResult,
  AgentPermissionListResult,
  AgentPermissionSetParams,
  AgentPermissionSetResult,
  AgentProjectParams,
  AgentSessionResult,
  AgentToolsResult,
  AgentTraceExportParams,
  AgentTraceExportResult,
  AgentTraceParams,
  AgentTraceResult,
  AgentTurnParams,
  AgentTurnResult,
  BenchmarkLookupParams,
  BenchmarkLookupResult,
  BenchmarkPackImportResult,
  BenchmarkPackListResult,
  BudgetResult,
  HealthResult,
  PingResult,
  Project,
  ProjectBriefSaveParams,
  ProjectBriefSaveResult,
  ProjectDataParams,
  ProjectDataResult,
  ProjectResult,
  ProjectScenarioSaveParams,
  ProjectScenarioSaveResult,
  ProjectSimulateParams,
  ProjectSimulateResult,
  ProviderCatalogResult,
  ProviderChatParams,
  ProviderChatResult,
  ProviderModelsResult,
  ProviderProfile,
  ProviderProfileListResult,
  ProviderProfileSaveParams,
  ProviderTestResult,
  ProviderUsageResult,
  RoleAssignment,
  RoleAssignmentResult,
  RoleListResult,
  RoleName,
  SandboxAnalysis,
  SandboxAnalyzeParams,
  SandboxAnalyzeResult,
  SandboxAuditExportParams,
  SandboxAuditExportResult,
  SandboxAuditListParams,
  SandboxAuditListResult,
  SandboxAuditRecordParams,
  SandboxAuditRecordResult,
  SidecarStatus,
  SimulationCancelled,
  SimulationDone,
  SimulationError,
  SimulationPartial,
  SimulationProgress,
  SimulationResult,
  SimulationStartParams,
  SimulationStartResult,
} from "@see/protocol";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

export const ipcAvailable = isTauri();

export function getSidecarStatus(): Promise<SidecarStatus> {
  return invoke<SidecarStatus>("sidecar_status");
}

export function getSidecarHealth(): Promise<HealthResult> {
  return invoke<HealthResult>("sidecar_health");
}

export function pingSidecar(echo?: string): Promise<PingResult> {
  return invoke<PingResult>("sidecar_ping", { echo: echo ?? null });
}

export function restartSidecar(): Promise<SidecarStatus> {
  return invoke<SidecarStatus>("sidecar_restart");
}

export function shutdownSidecar(): Promise<void> {
  return invoke<void>("sidecar_shutdown");
}

export function listProjects(): Promise<{ projects: Project[] }> {
  return invoke("project_list", { includeArchived: false });
}

export function createProject(name: string, description?: string): Promise<ProjectResult> {
  return invoke("project_create", { name, description: description ?? "" });
}

export function getProjectData(params: ProjectDataParams): Promise<ProjectDataResult> {
  return invoke("project_data", { params });
}

export function saveProjectBrief(
  params: ProjectBriefSaveParams,
): Promise<ProjectBriefSaveResult> {
  return invoke("project_brief_save", { params });
}

export function saveProjectScenario(
  params: ProjectScenarioSaveParams,
): Promise<ProjectScenarioSaveResult> {
  return invoke("project_scenario_save", { params });
}

export function simulateProject(
  params: ProjectSimulateParams,
): Promise<ProjectSimulateResult> {
  return invoke("project_simulate", { params });
}

export function onSimulationProgress(
  handler: (progress: number) => void,
): Promise<UnlistenFn> {
  if (!ipcAvailable) return Promise.resolve(() => undefined);
  return listen<{ progress: number }>("simulation:progress", (event) =>
    handler(event.payload.progress),
  );
}

export type SimulationEvent =
  | { method: "simulation.progress"; params: SimulationProgress }
  | { method: "simulation.partial"; params: SimulationPartial }
  | { method: "simulation.done"; params: SimulationDone }
  | { method: "simulation.cancelled"; params: SimulationCancelled }
  | { method: "simulation.error"; params: SimulationError };

type SimulationHandler = (event: SimulationEvent) => void;

const simulationHandlers = new Set<SimulationHandler>();
let simulationUnlisten: Promise<UnlistenFn> | null = null;
let activeSimulationRun: string | null = null;
let lastSimulationSeq = 0;
let pendingPartial: Extract<SimulationEvent, { method: "simulation.partial" }> | null =
  null;
let partialFrame: number | null = null;
let webRunCounter = 0;
let webTimers: ReturnType<typeof setTimeout>[] = [];

function publishSimulation(event: SimulationEvent): void {
  for (const handler of [...simulationHandlers]) handler(event);
}

function cancelScheduledPartial(): void {
  if (partialFrame === null) return;
  if (typeof cancelAnimationFrame === "function") cancelAnimationFrame(partialFrame);
  partialFrame = null;
}

function flushPartial(): void {
  if (pendingPartial === null) return;
  const event = pendingPartial;
  pendingPartial = null;
  publishSimulation(event);
}

function schedulePartial(
  event: Extract<SimulationEvent, { method: "simulation.partial" }>,
): void {
  pendingPartial = event;
  if (partialFrame !== null) return;
  if (typeof requestAnimationFrame === "function") {
    partialFrame = requestAnimationFrame(() => {
      partialFrame = null;
      flushPartial();
    });
    return;
  }
  partialFrame = 0;
  queueMicrotask(() => {
    partialFrame = null;
    flushPartial();
  });
}

function terminalSimulation(event: SimulationEvent): void {
  cancelScheduledPartial();
  flushPartial();
  publishSimulation(event);
  activeSimulationRun = null;
}

function dispatchSimulationEvent(event: SimulationEvent): void {
  const { runId } = event.params;
  if (activeSimulationRun === null || runId !== activeSimulationRun) return;

  if (event.method === "simulation.progress") {
    publishSimulation(event);
    return;
  }

  if (event.method === "simulation.partial") {
    if (event.params.seq <= lastSimulationSeq) return;
    lastSimulationSeq = event.params.seq;
    schedulePartial(event);
    return;
  }

  if (event.method === "simulation.done") {
    if (event.params.seq < lastSimulationSeq) return;
    lastSimulationSeq = Math.max(lastSimulationSeq, event.params.seq);
  }

  terminalSimulation(event);
}

/**
 * Démarre un calcul asynchrone. La promesse ne dure que le temps de
 * l'accusé de réception : les résultats arrivent via `onSimulationEvent`.
 */
export function startSimulation(
  params: SimulationStartParams,
): Promise<SimulationStartResult> {
  if (!ipcAvailable) return Promise.resolve(startWebSimulation(params));
  return invoke<SimulationStartResult>("simulation_start", { params }).then((result) => {
    activeSimulationRun = result.runId;
    lastSimulationSeq = 0;
    pendingPartial = null;
    cancelScheduledPartial();
    return result;
  });
}

export function cancelSimulation(runId: string): Promise<void> {
  if (!ipcAvailable) {
    cancelWebSimulation(runId);
    return Promise.resolve();
  }
  return invoke<unknown>("simulation_cancel", { runId }).then(() => undefined);
}

/**
 * Abonnement unique au flux de simulation. Le premier appel crée le listener
 * Tauri ; les suivants partagent le même. Le filtrage par run et par `seq`
 * vit ici, pas dans les composants.
 */
export function onSimulationEvent(
  handler: SimulationHandler,
): Promise<UnlistenFn> {
  simulationHandlers.add(handler);
  if (ipcAvailable && simulationUnlisten === null) {
    simulationUnlisten = listen<SimulationEvent>("simulation:event", (event) =>
      dispatchSimulationEvent(event.payload),
    ).catch((error) => {
      simulationUnlisten = null;
      throw error;
    });
  }
  return Promise.resolve(() => {
    simulationHandlers.delete(handler);
    if (simulationHandlers.size === 0 && simulationUnlisten !== null) {
      const stop = simulationUnlisten;
      simulationUnlisten = null;
      stop.then((unlisten) => unlisten()).catch(() => undefined);
    }
  });
}

function zeroConvergence() {
  return {
    converged: false,
    stability: 0,
    maxRelativeChange: 0,
    stableBlocks: 0,
  };
}

function clearWebTimers(): void {
  for (const timer of webTimers) clearTimeout(timer);
  webTimers = [];
}

function startWebSimulation(params: SimulationStartParams): SimulationStartResult {
  clearWebTimers();
  const runId = `web-${++webRunCounter}`;
  activeSimulationRun = runId;
  lastSimulationSeq = 0;
  const totalRuns = params.quality === "draft" ? 500 : 5_000;
  const convergence = zeroConvergence();
  const result = {
    runId,
    engineVersion: "web-shim",
    scenarioName: params.scenario.name,
    model: params.scenario.model ?? "retail_depot",
    currency: params.scenario.currency ?? "XOF",
    horizonMonths: params.scenario.horizonMonths ?? 36,
    runs: totalRuns,
    seed: params.seed,
    durationMs: 0,
    metrics: {},
    histogram: {},
    monthly: {},
    sensitivity: [],
    breakEven: {},
  } as unknown as SimulationResult;
  const aggregates = {
    completedRuns: totalRuns,
    totalRuns,
    metrics: {},
    histogram: {},
    monthly: {},
    convergence,
  } as unknown as SimulationPartial["aggregates"];

  webTimers.push(
    setTimeout(
      () =>
        dispatchSimulationEvent({
          method: "simulation.progress",
          params: {
            runId,
            completedRuns: 0,
            totalRuns,
            fraction: 0,
            block: 0,
            convergence,
          },
        }),
      0,
    ),
  );
  webTimers.push(
    setTimeout(
      () =>
        dispatchSimulationEvent({
          method: "simulation.partial",
          params: { runId, seq: 1, aggregates },
        }),
      10,
    ),
  );
  webTimers.push(
    setTimeout(
      () =>
        dispatchSimulationEvent({
          method: "simulation.done",
          params: { runId, seq: 1, result, persisted: false },
        }),
      20,
    ),
  );
  return { runId, accepted: true };
}

function cancelWebSimulation(runId: string): void {
  if (activeSimulationRun !== runId) return;
  clearWebTimers();
  dispatchSimulationEvent({
    method: "simulation.cancelled",
    params: { runId, reason: "simulation_cancelled" },
  });
}

function providerCall<T>(method: string, params: Record<string, unknown>): Promise<T> {
  return invoke<T>("provider_call", { method, params });
}

export function providerCatalog(): Promise<ProviderCatalogResult> {
  return providerCall("provider.catalog", {});
}

export function listProfiles(projectId: string): Promise<ProviderProfileListResult> {
  return providerCall("provider.profile.list", { projectId });
}

export function saveProfile(
  params: ProviderProfileSaveParams,
): Promise<{ profile: ProviderProfile }> {
  return invoke("provider_profile_save", { params });
}

export function deleteProfile(
  projectId: string,
  profileId: string,
): Promise<{ deleted: boolean }> {
  return invoke("provider_profile_delete", { projectId, profileId });
}

export function setProviderKey(keychainRef: string, secret: string): Promise<void> {
  return invoke("provider_key_set", { keychainRef, secret });
}

export function providerKeyStatus(keychainRef: string): Promise<boolean> {
  return invoke("provider_key_status", { keychainRef });
}

export function deleteProviderKey(keychainRef: string): Promise<void> {
  return invoke("provider_key_delete", { keychainRef });
}

export function testProvider(profile: ProviderProfile): Promise<ProviderTestResult> {
  return invoke("provider_test", { params: { profile } });
}

export function listProviderModels(profile: ProviderProfile): Promise<ProviderModelsResult> {
  return invoke("provider_models", { params: { profile } });
}

export function providerChat(params: ProviderChatParams): Promise<ProviderChatResult> {
  return invoke("provider_chat", { params });
}

export function listRoles(projectId: string): Promise<RoleListResult> {
  return providerCall("provider.role.list", { projectId });
}

export function setRole(
  projectId: string,
  role: RoleName,
  providerProfileId: string,
  model: string,
): Promise<RoleAssignmentResult> {
  return providerCall("provider.role.set", { projectId, role, providerProfileId, model });
}

export function deleteRole(projectId: string, role: RoleName): Promise<{ deleted: boolean }> {
  return providerCall("provider.role.delete", { projectId, role });
}

export function providerUsage(projectId: string): Promise<ProviderUsageResult> {
  return providerCall("provider.usage", { projectId });
}

export function providerBudget(projectId: string): Promise<BudgetResult> {
  return providerCall("provider.budget.get", { projectId });
}

export function setProviderBudget(
  projectId: string,
  limitMicros: number,
): Promise<BudgetResult> {
  return providerCall("provider.budget.set", { projectId, limitMicros });
}

export function deleteProviderBudget(projectId: string): Promise<{ deleted: boolean }> {
  return providerCall("provider.budget.delete", { projectId });
}

function agentCall<T>(method: string, params: object): Promise<T> {
  return invoke<T>("agent_call", { method, params: params as Record<string, unknown> });
}

export function agentState(params: AgentProjectParams): Promise<AgentSessionResult> {
  return agentCall("agent.state", params);
}

export function startAgent(params: AgentProjectParams): Promise<AgentSessionResult> {
  return agentCall("agent.start", params);
}

export function resetAgent(params: AgentProjectParams): Promise<AgentSessionResult> {
  return agentCall("agent.reset", params);
}

export function agentTurn(params: AgentTurnParams): Promise<AgentTurnResult> {
  return invoke("agent_turn", { params });
}

export function listAgentPermissions(
  params: AgentProjectParams,
): Promise<AgentPermissionListResult> {
  return agentCall("agent.permission.list", params);
}

export function setAgentPermission(
  params: AgentPermissionSetParams,
): Promise<AgentPermissionSetResult> {
  return agentCall("agent.permission.set", params);
}

export function deleteAgentPermission(
  params: AgentPermissionDeleteParams,
): Promise<AgentPermissionDeleteResult> {
  return agentCall("agent.permission.delete", params);
}

export function agentTrace(params: AgentTraceParams): Promise<AgentTraceResult> {
  return agentCall("agent.trace", params);
}

export function exportAgentTrace(
  params: AgentTraceExportParams,
): Promise<AgentTraceExportResult> {
  return agentCall("agent.trace.export", params);
}

export function agentTools(): Promise<AgentToolsResult> {
  return agentCall("agent.tools", {});
}

function sandboxCall<T>(method: string, params: object): Promise<T> {
  return invoke<T>("sandbox_call", { method, params: params as Record<string, unknown> });
}

export function analyzeSandboxCode(
  params: SandboxAnalyzeParams,
): Promise<SandboxAnalyzeResult> {
  return sandboxCall("sandbox.analyze", params);
}

export function recordSandboxAudit(
  params: SandboxAuditRecordParams,
): Promise<SandboxAuditRecordResult> {
  return sandboxCall("sandbox.audit.record", params);
}

export function listSandboxAudit(
  params: SandboxAuditListParams,
): Promise<SandboxAuditListResult> {
  return sandboxCall("sandbox.audit.list", params);
}

export function exportSandboxAudit(
  params: SandboxAuditExportParams,
): Promise<SandboxAuditExportResult> {
  return sandboxCall("sandbox.audit.export", params);
}

function benchmarkCall<T>(method: string, params: object): Promise<T> {
  return invoke<T>("benchmark_call", { method, params: params as Record<string, unknown> });
}

export function benchmarkLookup(
  params: BenchmarkLookupParams,
): Promise<BenchmarkLookupResult> {
  return benchmarkCall("benchmark.lookup", params);
}

export function listBenchmarkPacks(): Promise<BenchmarkPackListResult> {
  return benchmarkCall("benchmark.pack.list", {});
}

export function importBenchmarkPack(path: string): Promise<BenchmarkPackImportResult> {
  return benchmarkCall("benchmark.pack.import", { path });
}

export type { RoleAssignment, SandboxAnalysis };
