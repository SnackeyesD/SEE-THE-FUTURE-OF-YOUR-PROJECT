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
  SidecarStatus,
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

export type { RoleAssignment };
