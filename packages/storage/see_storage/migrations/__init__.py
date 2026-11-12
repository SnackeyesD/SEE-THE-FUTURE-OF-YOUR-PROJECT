from __future__ import annotations

MIGRATION_0001 = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    currency TEXT NOT NULL DEFAULT 'XOF',
    sector TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived', 'trashed')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1,
    engine_version TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content TEXT NOT NULL,
    token_count INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS briefs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    content_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'validated', 'archived')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (project_id, version)
);

CREATE TABLE IF NOT EXISTS scenarios (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    model TEXT NOT NULL,
    scenario_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scenario_id TEXT REFERENCES scenarios(id) ON DELETE SET NULL,
    engine_version TEXT NOT NULL,
    seed INTEGER,
    runs INTEGER NOT NULL,
    duration_ms REAL,
    summary_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT,
    result_path TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_profiles (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    base_url TEXT,
    model TEXT,
    keychain_ref TEXT,
    capabilities_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (project_id, name)
);

CREATE TABLE IF NOT EXISTS usage_log (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    provider_profile_id TEXT REFERENCES provider_profiles(id) ON DELETE SET NULL,
    kind TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_micros INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_permissions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    tool TEXT NOT NULL,
    scope TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('allow', 'ask', 'deny')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (project_id, tool, scope)
);

CREATE TABLE IF NOT EXISTS benchmark_packs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    path TEXT NOT NULL,
    checksum TEXT NOT NULL,
    source TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (name, version)
);

CREATE INDEX IF NOT EXISTS idx_messages_project_created
    ON messages(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_briefs_project_version
    ON briefs(project_id, version DESC);
CREATE INDEX IF NOT EXISTS idx_scenarios_project_created
    ON scenarios(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_runs_project_created
    ON simulation_runs(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_project_created
    ON usage_log(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_permissions_project
    ON tool_permissions(project_id);
"""

MIGRATION_0002 = """
CREATE TABLE IF NOT EXISTS role_assignments (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    role TEXT NOT NULL
        CHECK (role IN ('interviewer', 'modeler', 'narrator', 'delegate', 'coder')),
    provider_profile_id TEXT NOT NULL
        REFERENCES provider_profiles(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (project_id, role)
);

CREATE TABLE IF NOT EXISTS project_budgets (
    project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    limit_micros INTEGER NOT NULL DEFAULT 0 CHECK (limit_micros >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_role_assignments_project
    ON role_assignments(project_id);
"""

MIGRATION_0003 = """
CREATE TABLE IF NOT EXISTS agent_sessions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
    state TEXT NOT NULL CHECK (
        state IN (
            'idea', 'interviewing', 'brief_draft', 'brief_validated',
            'hypotheses_set', 'simulating', 'results_ready', 'narrating', 'done'
        )
    ),
    role TEXT NOT NULL
        CHECK (role IN ('interviewer', 'modeler', 'narrator', 'delegate', 'coder')),
    thread_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_trace (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    session_id TEXT REFERENCES agent_sessions(id) ON DELETE SET NULL,
    turn INTEGER NOT NULL DEFAULT 0 CHECK (turn >= 0),
    event_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS permission_events (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    tool TEXT NOT NULL,
    scope TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('allow', 'ask', 'deny')),
    reason TEXT,
    actor TEXT NOT NULL DEFAULT 'agent',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_trace_project_created
    ON agent_trace(project_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_permission_events_project_created
    ON permission_events(project_id, created_at DESC);
"""

MIGRATION_0004 = """
CREATE TABLE IF NOT EXISTS sandbox_audit (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT '',
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    status TEXT NOT NULL CHECK (
        status IN ('succeeded', 'failed', 'timeout', 'cancelled', 'rejected')
    ),
    analysis_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT,
    error TEXT,
    duration_ms REAL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sandbox_audit_project_created
    ON sandbox_audit(project_id, created_at DESC, id);
"""

MIGRATION_0005 = """
ALTER TABLE benchmark_packs ADD COLUMN pack_id TEXT;
ALTER TABLE benchmark_packs ADD COLUMN published_at TEXT;
ALTER TABLE benchmark_packs ADD COLUMN installed_at TEXT;
ALTER TABLE benchmark_packs ADD COLUMN signature TEXT;
ALTER TABLE benchmark_packs ADD COLUMN key_id TEXT;
ALTER TABLE benchmark_packs ADD COLUMN status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE benchmark_packs ADD COLUMN country TEXT;
ALTER TABLE benchmark_packs ADD COLUMN region TEXT;
ALTER TABLE benchmark_packs ADD COLUMN sector TEXT;
ALTER TABLE benchmark_packs ADD COLUMN subsector TEXT;
ALTER TABLE benchmark_packs ADD COLUMN value_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE benchmark_packs ADD COLUMN error TEXT;

CREATE TABLE IF NOT EXISTS benchmark_pack_events (
    id TEXT PRIMARY KEY,
    pack_id TEXT,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('installed', 'replaced', 'rejected', 'removed')),
    checksum TEXT,
    key_id TEXT,
    reason TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_benchmark_packs_pack_id
    ON benchmark_packs(pack_id);
CREATE INDEX IF NOT EXISTS idx_benchmark_pack_events_created
    ON benchmark_pack_events(created_at DESC, id DESC);
"""

MIGRATIONS: tuple[tuple[int, str], ...] = (
    (1, MIGRATION_0001),
    (2, MIGRATION_0002),
    (3, MIGRATION_0003),
    (4, MIGRATION_0004),
    (5, MIGRATION_0005),
)

LATEST_SCHEMA_VERSION = max(version for version, _ in MIGRATIONS)
