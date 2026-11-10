// AUTO-GENERATED FILE — DO NOT EDIT BY HAND.
// Source: packages/protocol/schema/messages.schema.json
// Protocol version: 1.6.0
// Regenerate with: npm run protocol:generate

export const PROTOCOL_VERSION = "1.6.0";

export type RequestId = number | string;

export interface JSONRPCErrorObject {
  code: number;
  message: string;
  data?: unknown;
}

export interface JSONRPCRequest {
  jsonrpc: "2.0";
  id?: RequestId;
  method: string;
  params?: Record<string, unknown>;
}

export interface JSONRPCResponse {
  jsonrpc: "2.0";
  id: RequestId;
  result?: unknown;
  error?: JSONRPCErrorObject;
}

export type MethodName = "ping" | "health" | "log" | "shutdown" | "simulate" | "simulate.progress" | "project.list" | "project.create" | "project.open" | "project.rename" | "project.duplicate" | "project.archive" | "project.restore" | "project.trash" | "project.delete" | "project.export" | "project.import" | "project.size" | "project.data" | "project.brief.save" | "project.scenario.save" | "project.simulate" | "integrity.check" | "storage.backup" | "provider.catalog" | "provider.profile.list" | "provider.profile.save" | "provider.profile.delete" | "provider.role.list" | "provider.role.set" | "provider.role.delete" | "provider.test" | "provider.models" | "provider.chat" | "provider.usage" | "provider.budget.get" | "provider.budget.set" | "provider.budget.delete" | "agent.prepare" | "agent.state" | "agent.start" | "agent.reset" | "agent.turn" | "agent.permission.list" | "agent.permission.set" | "agent.permission.delete" | "agent.trace" | "agent.trace.export" | "agent.tools";

export interface PingParams {
  echo?: string;
}

export interface PingResult {
  pong: boolean;
  echo?: string;
  timestamp: string;
}

export interface HealthResult {
  status: string;
  sidecarVersion: string;
  protocolVersion: string;
  pid: number;
  python: string;
}

export interface LogParams {
  level: "debug" | "info" | "warn" | "error";
  message: string;
}

export interface LogResult {
  logged: boolean;
}

export interface ShutdownResult {
  ok: boolean;
}

export interface SidecarStatus {
  running: boolean;
  pid?: number;
  error?: string;
}

export interface DistributionSpec {
  kind: "normal" | "lognormal" | "triangular" | "uniform" | "poisson" | "empirical";
  mean?: number;
  std?: number;
  sigma?: number;
  low?: number;
  mode?: number;
  high?: number;
  values?: number[];
  weights?: number[];
}

export interface Hypothesis {
  value: number;
  distribution?: DistributionSpec;
  source?: string;
  confidence?: number;
  min?: number;
  max?: number;
  description?: string;
}

export interface Scenario {
  schemaVersion?: "1.0.0";
  name: string;
  model?: "retail_depot";
  currency?: string;
  horizonMonths?: number;
  assumptions?: Record<string, Hypothesis>;
  seasonality?: number[] | null;
  notes?: string;
}

export interface SimulationConfig {
  runs?: number;
  seed?: number;
  batchSize?: number;
  histogramBins?: number;
}

export interface Metrics {
  meanProfit: number;
  medianProfit: number;
  stdProfit: number;
  minProfit: number;
  maxProfit: number;
  p10: number;
  p50: number;
  p90: number;
  lossProbability: number;
  profitPositiveProbability: number;
  meanRevenue: number;
  meanCosts: number;
  meanTax: number;
  meanCashEnd: number;
  meanUnitsSold: number;
  meanUnitsLost: number;
  meanStockoutMonths: number;
  meanEndStock: number;
  meanInventoryValue: number;
  meanProfitMargin: number;
}

export interface HistogramBin {
  lower: number;
  upper: number;
  count: number;
  probability: number;
}

export interface Histogram {
  bins: HistogramBin[];
}

export interface MonthlyAverage {
  index: number;
  month: number;
  meanRevenue: number;
  meanProfit: number;
  meanDemand: number;
  meanUnitsSold: number;
  meanStockEnd: number;
  stockoutProbability: number;
}

export interface MonthlyAverages {
  values: MonthlyAverage[];
}

export interface SensitivityEntry {
  hypothesis: string;
  correlation: number;
  contribution: number;
}

export interface BreakEven {
  monthlyFixedCosts: number;
  unitMargin: number;
  breakEvenUnitsMonthly: number | null;
  breakEvenRevenueMonthly: number | null;
}

export interface SimulationResult {
  runId: string;
  engineVersion: string;
  scenarioName: string;
  model: string;
  currency: string;
  horizonMonths: number;
  runs: number;
  seed: number;
  durationMs: number;
  metrics: Metrics;
  histogram: Histogram;
  monthly: MonthlyAverages;
  sensitivity: SensitivityEntry[];
  breakEven: BreakEven;
}

export interface SimulateParams {
  scenario: Scenario;
  config?: SimulationConfig;
  progress?: boolean;
}

export interface SimulateProgressParams {
  progress: number;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  currency: string;
  sector?: string | null;
  status: "active" | "archived" | "trashed";
  createdAt: string;
  updatedAt: string;
  schemaVersion: number;
  engineVersion?: string | null;
  metadata: Record<string, unknown>;
  deletedAt?: string | null;
}

export interface ProjectListParams {
  includeArchived?: boolean;
  includeTrashed?: boolean;
}

export interface ProjectCreateParams {
  name: string;
  description?: string;
  currency?: string;
  sector?: string | null;
}

export interface ProjectIdParams {
  projectId: string;
}

export interface ProjectRenameParams {
  projectId: string;
  name: string;
}

export interface ProjectDuplicateParams {
  projectId: string;
  name?: string;
}

export interface ProjectExportParams {
  projectId: string;
  destination: string;
}

export interface ProjectImportParams {
  source: string;
  name?: string;
}

export interface ProjectResult {
  project: Project;
}

export interface ProjectListResult {
  projects: Project[];
}

export interface ProjectDeleteResult {
  deleted: boolean;
}

export interface ProjectExportResult {
  path: string;
  checksum: string;
  bytes: number;
}

export interface ProjectSizeResult {
  databaseBytes: number;
  resultsBytes: number;
  totalBytes: number;
}

export interface IntegrityCheckResult {
  ok: boolean;
  message: string;
}

export interface BriefRecord {
  id: string;
  projectId: string;
  version: number;
  content: Record<string, unknown>;
  status: string;
  createdAt: string;
  updatedAt: string;
}

export interface ScenarioRecord {
  id: string;
  projectId: string;
  name: string;
  model: string;
  scenario: Scenario;
  createdAt: string;
  updatedAt: string;
}

export interface SimulationRunRecord {
  id: string;
  projectId: string;
  scenarioId: string | null;
  engineVersion: string;
  seed: number | null;
  runs: number;
  durationMs: number | null;
  summary: Record<string, unknown>;
  result: SimulationResult | null;
  createdAt: string;
}

export interface ProjectDataParams {
  projectId: string;
}

export interface ProjectDataResult {
  projectId: string;
  brief: BriefRecord | null;
  scenario: ScenarioRecord | null;
  run: SimulationRunRecord | null;
}

export interface ProjectBriefSaveParams {
  projectId: string;
  content: Record<string, unknown>;
  status?: "draft" | "validated";
}

export interface ProjectBriefSaveResult {
  brief: BriefRecord;
}

export interface ProjectScenarioSaveParams {
  projectId: string;
  name: string;
  model?: string;
  scenario: Scenario;
}

export interface ProjectScenarioSaveResult {
  scenario: ScenarioRecord;
}

export interface ProjectSimulateParams {
  projectId: string;
  scenario?: Scenario;
  config?: SimulationConfig;
  progress?: boolean;
}

export interface ProjectSimulateResult {
  run: SimulationRunRecord;
  scenario: ScenarioRecord;
  result: SimulationResult;
}

export interface BackupParams {
  destination?: string;
}

export interface BackupResult {
  path: string;
}

export type ProviderId = string;

export interface ProviderCatalogEntry {
  id: string;
  label: string;
  kind: string;
  baseUrl?: string | null;
  requiresKey: boolean;
  defaultModel?: string | null;
  capabilitiesVersion: string;
}

export interface ProviderCatalogResult {
  providers: ProviderCatalogEntry[];
  capabilitiesVersion: string;
}

export interface ProviderCapabilities {
  contextWindow?: number | null;
  nativeTools: boolean;
  nativeStructuredOutput: boolean;
  reasoning: boolean;
  vision: boolean;
  inputPricePerMillion?: number | null;
  outputPricePerMillion?: number | null;
  currency?: string;
  source?: string;
  version?: string;
}

export interface ProviderModelInfo {
  id: string;
  name?: string | null;
  capabilities: ProviderCapabilities;
}

export interface ProviderProfile {
  id: string;
  projectId: string;
  name: string;
  provider: string;
  baseUrl?: string | null;
  model?: string | null;
  keychainRef?: string | null;
  capabilities: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface ProviderProfileListParams {
  projectId: string;
}

export interface ProviderProfileListResult {
  profiles: ProviderProfile[];
}

export interface ProviderProfileSaveParams {
  projectId: string;
  name: string;
  provider: string;
  baseUrl?: string | null;
  model?: string | null;
  keychainRef?: string | null;
  capabilities?: Record<string, unknown>;
}

export interface ProviderProfileDeleteParams {
  profileId: string;
}

export interface ProviderProfileResult {
  profile: ProviderProfile;
}

export interface ProviderDeleteResult {
  deleted: boolean;
}

export type RoleName = "interviewer" | "modeler" | "narrator" | "delegate" | "coder";

export interface RoleAssignment {
  id: string;
  projectId: string;
  role: RoleName;
  providerProfileId: string;
  model: string;
  createdAt: string;
  updatedAt: string;
}

export interface RoleListParams {
  projectId: string;
}

export interface RoleListResult {
  assignments: RoleAssignment[];
}

export interface RoleSetParams {
  projectId: string;
  role: RoleName;
  providerProfileId: string;
  model: string;
}

export interface RoleDeleteParams {
  projectId: string;
  role: RoleName;
}

export interface RoleAssignmentResult {
  assignment: RoleAssignment;
}

export interface ChatMessageInput {
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  name?: string | null;
  toolCallId?: string | null;
  toolCalls?: ProviderToolCall[];
}

export interface ProviderToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface ProviderToolDefinition {
  name: string;
  description?: string;
  parameters?: Record<string, unknown>;
}

export interface ProviderChatRequest {
  model: string;
  messages: ChatMessageInput[];
  temperature?: number;
  maxTokens?: number | null;
  tools?: ProviderToolDefinition[];
  responseFormat?: "text" | "json";
}

export interface ProviderChatParams {
  projectId: string;
  profile: ProviderProfile;
  apiKey?: string | null;
  request: ProviderChatRequest;
}

export interface ProviderTokenUsage {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  costMicros: number;
  currency: string;
}

export interface ProviderFallback {
  provider: string;
  reason: string;
}

export interface ProviderChatResult {
  text: string;
  reasoning?: string;
  toolCalls: ProviderToolCall[];
  usage: ProviderTokenUsage;
  provider: string;
  model: string;
  finishReason?: string | null;
  fallbacks?: ProviderFallback[];
  budget?: BudgetResult;
}

export interface ProviderTestParams {
  profile: ProviderProfile;
  apiKey?: string | null;
}

export interface ProviderTestResult {
  ok: boolean;
  message: string;
  latencyMs: number;
  models: ProviderModelInfo[];
}

export interface ProviderModelsParams {
  profile: ProviderProfile;
  apiKey?: string | null;
}

export interface ProviderModelsResult {
  models: ProviderModelInfo[];
}

export interface ProviderUsageParams {
  projectId: string;
}

export interface ProviderUsageEntry {
  id: string;
  providerProfileId?: string | null;
  kind: string;
  inputTokens: number;
  outputTokens: number;
  costMicros: number;
  metadata?: Record<string, unknown>;
  createdAt: string;
}

export interface ProviderUsageResult {
  entries: ProviderUsageEntry[];
  inputTokens: number;
  outputTokens: number;
  costMicros: number;
}

export interface BudgetParams {
  projectId: string;
}

export interface BudgetSetParams {
  projectId: string;
  limitMicros: number;
}

export interface BudgetResult {
  projectId: string;
  limitMicros: number;
  spentMicros: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export type AgentStateName = "idea" | "interviewing" | "brief_draft" | "brief_validated" | "hypotheses_set" | "simulating" | "results_ready" | "narrating" | "done";

export type AgentPermissionMode = "allow" | "ask" | "deny";

export type AgentTurnStatus = "text" | "permission_required" | "requires_review" | "permission_denied" | "tool_error" | "max_iterations";

export interface AgentSession {
  id?: string | null;
  projectId: string;
  state: AgentStateName;
  role: RoleName;
  thread: ChatMessageInput[];
  createdAt: string | null;
  updatedAt: string | null;
}

export interface AgentProjectParams {
  projectId: string;
}

export interface AgentSessionResult {
  session: AgentSession;
}

export interface AgentPrepareParams {
  projectId: string;
  role?: RoleName;
}

export interface AgentPrepareResult {
  role: RoleName;
  model: string;
  profile: ProviderProfile;
  state: AgentStateName;
}

export interface AgentPendingPermission {
  tool: string;
  callId: string;
  decision: AgentPermissionMode;
  reason: string;
}

export interface AgentToolEvent {
  callId: string;
  tool: string;
  ok: boolean;
  result?: unknown;
  error?: Record<string, unknown> | null;
  requiresReview: boolean;
}

export interface AgentTurnParams {
  projectId: string;
  profile?: ProviderProfile;
  apiKey?: string | null;
  role?: RoleName;
  message?: string | null;
  approvals?: string[];
  maxIterations?: number;
  exportPath?: string | null;
}

export interface AgentTurnResult {
  status: AgentTurnStatus;
  role: RoleName;
  state: AgentStateName;
  text: string;
  pendingPermissions: AgentPendingPermission[];
  toolEvents: AgentToolEvent[];
  usage: Record<string, unknown>;
  budget: BudgetResult;
  session: AgentSession;
  projectId: string;
}

export interface AgentPermission {
  id: string;
  projectId: string;
  tool: string;
  scope: string;
  decision: AgentPermissionMode;
  createdAt: string;
  updatedAt: string;
}

export interface AgentPermissionEvent {
  id: string;
  projectId: string;
  tool: string;
  scope: string;
  decision: AgentPermissionMode;
  reason?: string | null;
  actor: "agent" | "user" | "system";
  createdAt: string;
}

export interface AgentPermissionListResult {
  permissions: AgentPermission[];
  defaults: Record<string, unknown>;
  alwaysAsk: string[];
  events: AgentPermissionEvent[];
}

export interface AgentPermissionSetParams {
  projectId: string;
  tool: string;
  scope?: string;
  decision: AgentPermissionMode;
  reason?: string | null;
}

export interface AgentPermissionSetResult {
  permission: AgentPermission;
  permissions: AgentPermission[];
  defaults: Record<string, unknown>;
  alwaysAsk: string[];
  events: AgentPermissionEvent[];
}

export interface AgentPermissionDeleteParams {
  projectId: string;
  tool: string;
  scope?: string;
}

export interface AgentPermissionDeleteResult {
  deleted: boolean;
  permissions: AgentPermission[];
  defaults: Record<string, unknown>;
  alwaysAsk: string[];
  events: AgentPermissionEvent[];
}

export interface AgentTraceParams {
  projectId: string;
  limit?: number;
}

export interface AgentTraceEntry {
  id: string;
  projectId: string;
  sessionId?: string | null;
  turn: number;
  event: Record<string, unknown>;
  createdAt: string;
}

export interface AgentTraceResult {
  events: AgentTraceEntry[];
  count: number;
}

export interface AgentTraceExportParams {
  projectId: string;
  destination: string;
}

export interface AgentTraceExportResult {
  path: string;
  count: number;
}

export interface AgentToolInfo {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  defaultPermission: AgentPermissionMode;
  alwaysAsk: boolean;
}

export interface AgentToolsResult {
  tools: AgentToolInfo[];
}

export interface SandboxIssue {
  code: string;
  message: string;
  line: number | null;
  column: number | null;
  severity: "error" | "warning";
}

export interface SandboxLimits {
  timeoutMs: number;
  workerStartTimeoutMs: number;
  memoryBytes: number;
  maxCodeBytes: number;
  maxInputBytes: number;
  maxOutputBytes: number;
  maxLogBytes: number;
}

export interface SandboxAnalysis {
  ok: boolean;
  codeHash: string;
  issues: SandboxIssue[];
  allowedImports: string[];
  limits: SandboxLimits;
}

export interface SandboxAnalyzeParams {
  code: string;
}

export interface SandboxAnalyzeResult {
  analysis: SandboxAnalysis;
}

export type SandboxDecision = "approved" | "rejected";

export type SandboxStatus = "succeeded" | "failed" | "timeout" | "cancelled" | "rejected";

export interface SandboxAuditRecord {
  id: string;
  projectId: string;
  code: string;
  codeHash: string;
  purpose: string;
  decision: SandboxDecision;
  status: SandboxStatus;
  analysis: SandboxAnalysis;
  result: Record<string, unknown> | null;
  error: string | null;
  durationMs: number | null;
  createdAt: string;
}

export interface SandboxAuditRecordParams {
  projectId: string;
  code: string;
  codeHash: string;
  purpose?: string;
  decision: SandboxDecision;
  status: SandboxStatus;
  result?: Record<string, unknown> | null;
  error?: string | null;
  durationMs?: number | null;
}

export interface SandboxAuditRecordResult {
  record: SandboxAuditRecord;
}

export interface SandboxAuditListParams {
  projectId: string;
  limit?: number;
}

export interface SandboxAuditListResult {
  records: SandboxAuditRecord[];
  count: number;
}

export interface SandboxAuditExportParams {
  projectId: string;
}

export interface SandboxAuditExportResult {
  path: string;
  count: number;
}
