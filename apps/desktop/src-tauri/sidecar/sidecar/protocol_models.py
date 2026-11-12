# AUTO-GENERATED FILE — DO NOT EDIT BY HAND.
# Source: packages/protocol/schema/messages.schema.json
# Protocol version: 1.7.0
# Regenerate with: npm run protocol:generate

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

PROTOCOL_VERSION = "1.7.0"

RequestId = int | str


class JSONRPCErrorObject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: int
    message: str
    data: Any = None


class JSONRPCRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"]
    id: RequestId | None = None
    method: str
    params: dict[str, Any] | None = None


class JSONRPCResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"]
    id: RequestId
    result: Any = None
    error: JSONRPCErrorObject | None = None


MethodName = Literal[
    "ping",
    "health",
    "log",
    "shutdown",
    "simulate",
    "simulate.progress",
    "project.list",
    "project.create",
    "project.open",
    "project.rename",
    "project.duplicate",
    "project.archive",
    "project.restore",
    "project.trash",
    "project.delete",
    "project.export",
    "project.import",
    "project.size",
    "project.data",
    "project.brief.save",
    "project.scenario.save",
    "project.simulate",
    "integrity.check",
    "storage.backup",
    "provider.catalog",
    "provider.profile.list",
    "provider.profile.save",
    "provider.profile.delete",
    "provider.role.list",
    "provider.role.set",
    "provider.role.delete",
    "provider.test",
    "provider.models",
    "provider.chat",
    "provider.usage",
    "provider.budget.get",
    "provider.budget.set",
    "provider.budget.delete",
    "agent.prepare",
    "agent.state",
    "agent.start",
    "agent.reset",
    "agent.turn",
    "agent.permission.list",
    "agent.permission.set",
    "agent.permission.delete",
    "agent.trace",
    "agent.trace.export",
    "agent.tools",
    "benchmark.lookup",
    "benchmark.pack.list",
    "benchmark.pack.import",
]


class PingParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    echo: str | None = None


class PingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pong: bool
    echo: str | None = None
    timestamp: str


class HealthResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    sidecarVersion: str
    protocolVersion: str
    pid: int
    python: str


class LogParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: Literal["debug", "info", "warn", "error"]
    message: str


class LogResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logged: bool


class ShutdownResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool


class SidecarStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    running: bool
    pid: int | None = None
    error: str | None = None


class DistributionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["normal", "lognormal", "triangular", "uniform", "poisson", "empirical"]
    mean: float | None = None
    std: float | None = None
    sigma: float | None = None
    low: float | None = None
    mode: float | None = None
    high: float | None = None
    values: list[float] | None = None
    weights: list[float] | None = None


class Hypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float
    distribution: DistributionSpec | None = None
    source: str | None = None
    confidence: float | None = None
    min: float | None = None
    max: float | None = None
    description: str | None = None
    provenance: BenchmarkProvenance | None = None


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: Literal["1.0.0"] | None = None
    name: str
    model: Literal["retail_depot"] | None = None
    currency: str | None = None
    horizonMonths: int | None = None
    assumptions: dict[str, Hypothesis] | None = None
    seasonality: list[float] | None = None
    notes: str | None = None


class SimulationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: int | None = None
    seed: int | None = None
    batchSize: int | None = None
    histogramBins: int | None = None


class Metrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meanProfit: float
    medianProfit: float
    stdProfit: float
    minProfit: float
    maxProfit: float
    p10: float
    p50: float
    p90: float
    lossProbability: float
    profitPositiveProbability: float
    meanRevenue: float
    meanCosts: float
    meanTax: float
    meanCashEnd: float
    meanUnitsSold: float
    meanUnitsLost: float
    meanStockoutMonths: float
    meanEndStock: float
    meanInventoryValue: float
    meanProfitMargin: float


class HistogramBin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lower: float
    upper: float
    count: int
    probability: float


class Histogram(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bins: list[HistogramBin]


class MonthlyAverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    month: int
    meanRevenue: float
    meanProfit: float
    meanDemand: float
    meanUnitsSold: float
    meanStockEnd: float
    stockoutProbability: float


class MonthlyAverages(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: list[MonthlyAverage]


class SensitivityEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis: str
    correlation: float
    contribution: float


class BreakEven(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monthlyFixedCosts: float
    unitMargin: float
    breakEvenUnitsMonthly: float | None
    breakEvenRevenueMonthly: float | None


class SimulationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runId: str
    engineVersion: str
    scenarioName: str
    model: str
    currency: str
    horizonMonths: int
    runs: int
    seed: int
    durationMs: float
    metrics: Metrics
    histogram: Histogram
    monthly: MonthlyAverages
    sensitivity: list[SensitivityEntry]
    breakEven: BreakEven


class SimulateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: Scenario
    config: SimulationConfig | None = None
    progress: bool | None = None


class SimulateProgressParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    progress: float


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str
    currency: str
    sector: str | None = None
    status: Literal["active", "archived", "trashed"]
    createdAt: str
    updatedAt: str
    schemaVersion: int
    engineVersion: str | None = None
    metadata: dict[str, Any]
    deletedAt: str | None = None


class ProjectListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    includeArchived: bool | None = None
    includeTrashed: bool | None = None


class ProjectCreateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    currency: str | None = None
    sector: str | None = None


class ProjectIdParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str


class ProjectRenameParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    name: str


class ProjectDuplicateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    name: str | None = None


class ProjectExportParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    destination: str


class ProjectImportParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    name: str | None = None


class ProjectResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: Project


class ProjectListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projects: list[Project]


class ProjectDeleteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: bool


class ProjectExportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    checksum: str
    bytes: int


class ProjectSizeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    databaseBytes: int
    resultsBytes: int
    totalBytes: int


class IntegrityCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    message: str


class BriefRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    projectId: str
    version: int
    content: dict[str, Any]
    status: str
    createdAt: str
    updatedAt: str


class ScenarioRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    projectId: str
    name: str
    model: str
    scenario: Scenario
    createdAt: str
    updatedAt: str


class SimulationRunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    projectId: str
    scenarioId: str | None
    engineVersion: str
    seed: int | None
    runs: int
    durationMs: float | None
    summary: dict[str, Any]
    result: SimulationResult | None
    createdAt: str


class ProjectDataParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str


class ProjectDataResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    brief: BriefRecord | None
    scenario: ScenarioRecord | None
    run: SimulationRunRecord | None


class ProjectBriefSaveParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    content: dict[str, Any]
    status: Literal["draft", "validated"] | None = None


class ProjectBriefSaveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brief: BriefRecord


class ProjectScenarioSaveParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    name: str
    model: str | None = None
    scenario: Scenario


class ProjectScenarioSaveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: ScenarioRecord


class ProjectSimulateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    scenario: Scenario | None = None
    config: SimulationConfig | None = None
    progress: bool | None = None


class ProjectSimulateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: SimulationRunRecord
    scenario: ScenarioRecord
    result: SimulationResult


class BackupParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: str | None = None


class BackupResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str


ProviderId = str


class ProviderCatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    kind: str
    baseUrl: str | None = None
    requiresKey: bool
    defaultModel: str | None = None
    capabilitiesVersion: str


class ProviderCatalogResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    providers: list[ProviderCatalogEntry]
    capabilitiesVersion: str


class ProviderCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contextWindow: int | None = None
    nativeTools: bool
    nativeStructuredOutput: bool
    reasoning: bool
    vision: bool
    inputPricePerMillion: float | None = None
    outputPricePerMillion: float | None = None
    currency: str | None = None
    source: str | None = None
    version: str | None = None


class ProviderModelInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str | None = None
    capabilities: ProviderCapabilities


class ProviderProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    projectId: str
    name: str
    provider: str
    baseUrl: str | None = None
    model: str | None = None
    keychainRef: str | None = None
    capabilities: dict[str, Any]
    createdAt: str
    updatedAt: str


class ProviderProfileListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str


class ProviderProfileListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profiles: list[ProviderProfile]


class ProviderProfileSaveParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    name: str
    provider: str
    baseUrl: str | None = None
    model: str | None = None
    keychainRef: str | None = None
    capabilities: dict[str, Any] | None = None


class ProviderProfileDeleteParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profileId: str


class ProviderProfileResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: ProviderProfile


class ProviderDeleteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: bool


RoleName = Literal[
    "interviewer",
    "modeler",
    "narrator",
    "delegate",
    "coder",
]


class RoleAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    projectId: str
    role: RoleName
    providerProfileId: str
    model: str
    createdAt: str
    updatedAt: str


class RoleListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str


class RoleListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignments: list[RoleAssignment]


class RoleSetParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    role: RoleName
    providerProfileId: str
    model: str


class RoleDeleteParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    role: RoleName


class RoleAssignmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment: RoleAssignment


class ChatMessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    toolCallId: str | None = None
    toolCalls: list[ProviderToolCall] | None = None


class ProviderToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    arguments: dict[str, Any]


class ProviderToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None


class ProviderChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    messages: list[ChatMessageInput]
    temperature: float | None = None
    maxTokens: int | None = None
    tools: list[ProviderToolDefinition] | None = None
    responseFormat: Literal["text", "json"] | None = None


class ProviderChatParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    profile: ProviderProfile
    apiKey: str | None = None
    request: ProviderChatRequest


class ProviderTokenUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inputTokens: int
    outputTokens: int
    totalTokens: int
    costMicros: int
    currency: str


class ProviderFallback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    reason: str


class ProviderChatResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    reasoning: str | None = None
    toolCalls: list[ProviderToolCall]
    usage: ProviderTokenUsage
    provider: str
    model: str
    finishReason: str | None = None
    fallbacks: list[ProviderFallback] | None = None
    budget: BudgetResult | None = None


class ProviderTestParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: ProviderProfile
    apiKey: str | None = None


class ProviderTestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    message: str
    latencyMs: float
    models: list[ProviderModelInfo]


class ProviderModelsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: ProviderProfile
    apiKey: str | None = None


class ProviderModelsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    models: list[ProviderModelInfo]


class ProviderUsageParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str


class ProviderUsageEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    providerProfileId: str | None = None
    kind: str
    inputTokens: int
    outputTokens: int
    costMicros: int
    metadata: dict[str, Any] | None = None
    createdAt: str


class ProviderUsageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[ProviderUsageEntry]
    inputTokens: int
    outputTokens: int
    costMicros: int


class BudgetParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str


class BudgetSetParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    limitMicros: int


class BudgetResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    limitMicros: int
    spentMicros: int
    createdAt: str | None = None
    updatedAt: str | None = None


AgentStateName = Literal[
    "idea",
    "interviewing",
    "brief_draft",
    "brief_validated",
    "hypotheses_set",
    "simulating",
    "results_ready",
    "narrating",
    "done",
]


AgentPermissionMode = Literal[
    "allow",
    "ask",
    "deny",
]


AgentTurnStatus = Literal[
    "text",
    "permission_required",
    "requires_review",
    "permission_denied",
    "tool_error",
    "max_iterations",
]


class AgentSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    projectId: str
    state: AgentStateName
    role: RoleName
    thread: list[ChatMessageInput]
    createdAt: str | None
    updatedAt: str | None


class AgentProjectParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str


class AgentSessionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session: AgentSession


class AgentPrepareParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    role: RoleName | None = None


class AgentPrepareResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: RoleName
    model: str
    profile: ProviderProfile
    state: AgentStateName


class AgentPendingPermission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    callId: str
    decision: AgentPermissionMode
    reason: str


class AgentToolEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    callId: str
    tool: str
    ok: bool
    result: Any = None
    error: dict[str, Any] | None = None
    requiresReview: bool


class AgentTurnParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    profile: ProviderProfile | None = None
    apiKey: str | None = None
    role: RoleName | None = None
    message: str | None = None
    approvals: list[str] | None = None
    maxIterations: int | None = None
    exportPath: str | None = None


class AgentTurnResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AgentTurnStatus
    role: RoleName
    state: AgentStateName
    text: str
    pendingPermissions: list[AgentPendingPermission]
    toolEvents: list[AgentToolEvent]
    usage: dict[str, Any]
    budget: BudgetResult
    session: AgentSession
    projectId: str


class AgentPermission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    projectId: str
    tool: str
    scope: str
    decision: AgentPermissionMode
    createdAt: str
    updatedAt: str


class AgentPermissionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    projectId: str
    tool: str
    scope: str
    decision: AgentPermissionMode
    reason: str | None = None
    actor: Literal["agent", "user", "system"]
    createdAt: str


class AgentPermissionListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permissions: list[AgentPermission]
    defaults: dict[str, Any]
    alwaysAsk: list[str]
    events: list[AgentPermissionEvent]


class AgentPermissionSetParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    tool: str
    scope: str | None = None
    decision: AgentPermissionMode
    reason: str | None = None


class AgentPermissionSetResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permission: AgentPermission
    permissions: list[AgentPermission]
    defaults: dict[str, Any]
    alwaysAsk: list[str]
    events: list[AgentPermissionEvent]


class AgentPermissionDeleteParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    tool: str
    scope: str | None = None


class AgentPermissionDeleteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: bool
    permissions: list[AgentPermission]
    defaults: dict[str, Any]
    alwaysAsk: list[str]
    events: list[AgentPermissionEvent]


class AgentTraceParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    limit: int | None = None


class AgentTraceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    projectId: str
    sessionId: str | None = None
    turn: int
    event: dict[str, Any]
    createdAt: str


class AgentTraceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[AgentTraceEntry]
    count: int


class AgentTraceExportParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    destination: str


class AgentTraceExportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    count: int


class AgentToolInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    parameters: dict[str, Any]
    defaultPermission: AgentPermissionMode
    alwaysAsk: bool


class AgentToolsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tools: list[AgentToolInfo]


class SandboxIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    line: int | None
    column: int | None
    severity: Literal["error", "warning"]


class SandboxLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeoutMs: int
    workerStartTimeoutMs: int
    memoryBytes: int
    maxCodeBytes: int
    maxInputBytes: int
    maxOutputBytes: int
    maxLogBytes: int


class SandboxAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    codeHash: str
    issues: list[SandboxIssue]
    allowedImports: list[str]
    limits: SandboxLimits


class SandboxAnalyzeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str


class SandboxAnalyzeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis: SandboxAnalysis


SandboxDecision = Literal[
    "approved",
    "rejected",
]


SandboxStatus = Literal[
    "succeeded",
    "failed",
    "timeout",
    "cancelled",
    "rejected",
]


class SandboxAuditRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    projectId: str
    code: str
    codeHash: str
    purpose: str
    decision: SandboxDecision
    status: SandboxStatus
    analysis: SandboxAnalysis
    result: dict[str, Any] | None
    error: str | None
    durationMs: float | None
    createdAt: str


class SandboxAuditRecordParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    code: str
    codeHash: str
    purpose: str | None = None
    decision: SandboxDecision
    status: SandboxStatus
    result: dict[str, Any] | None = None
    error: str | None = None
    durationMs: float | None = None


class SandboxAuditRecordResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record: SandboxAuditRecord


class SandboxAuditListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str
    limit: int | None = None


class SandboxAuditListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[SandboxAuditRecord]
    count: int


class SandboxAuditExportParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectId: str


class SandboxAuditExportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    count: int


BenchmarkReliability = Literal[
    "official",
    "study",
    "field",
    "estimate",
]


BenchmarkFreshness = Literal[
    "fresh",
    "aging",
    "stale",
]


BenchmarkFallback = Literal[
    "none",
    "country",
    "regional",
    "global",
]


class BenchmarkProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["benchmark", "user"]
    label: str
    indicator: str | None = None
    source: str | None = None
    sourceUrl: str | None = None
    sourceDate: str | None = None
    reliability: BenchmarkReliability | None = None
    freshness: BenchmarkFreshness | None = None
    packId: str | None = None
    packVersion: str | None = None
    packPublishedAt: str | None = None
    keyId: str | None = None
    checksum: str | None = None
    fallback: BenchmarkFallback | None = None
    conflicts: int | None = None


class BenchmarkRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indicator: str
    value: float
    unit: str
    currency: str
    country: str
    region: str | None = None
    regionGroup: str | None = None
    sector: str
    subsector: str | None = None
    source: str
    sourceUrl: str
    sourceDate: str
    reliability: BenchmarkReliability
    freshness: BenchmarkFreshness
    min: float | None = None
    max: float | None = None
    notes: str | None = None
    packId: str
    packVersion: str
    packPublishedAt: str
    keyId: str
    checksum: str
    fallback: BenchmarkFallback
    conflicts: int


class BenchmarkLookupParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indicator: str
    country: str | None = None
    region: str | None = None
    sector: str | None = None
    subsector: str | None = None
    asOf: str | None = None
    fromDate: str | None = None
    toDate: str | None = None
    allowFallback: bool | None = None


class BenchmarkLookupResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool
    record: BenchmarkRecord | None = None
    reason: str | None = None


class BenchmarkPackInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packId: str
    name: str
    version: str
    publishedAt: str
    country: str
    region: str | None = None
    currency: str
    sector: str
    subsector: str | None = None
    valueCount: int
    checksum: str
    keyId: str
    status: Literal["verified", "invalid", "unverified"]
    source: Literal["bundled", "user", "imported"]
    path: str | None = None
    error: str | None = None


BenchmarkPackListParams = dict[str, Any]


class BenchmarkPackListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packs: list[BenchmarkPackInfo]
    errors: list[str]


class BenchmarkPackImportParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str


class BenchmarkPackImportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pack: BenchmarkPackInfo
    replaced: bool | None = None
