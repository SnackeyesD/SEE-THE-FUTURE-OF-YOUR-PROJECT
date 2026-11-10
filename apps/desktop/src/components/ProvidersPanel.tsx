import type {
  BudgetResult,
  Project,
  ProviderCatalogEntry,
  ProviderCatalogResult,
  ProviderChatResult,
  ProviderModelInfo,
  ProviderProfile,
  ProviderTestResult,
  ProviderUsageResult,
  RoleAssignment,
  RoleName,
} from "@see/protocol";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createProject,
  deleteProfile,
  deleteProviderBudget,
  deleteRole,
  listProfiles,
  listProjects,
  listProviderModels,
  listRoles,
  providerBudget,
  providerCatalog,
  providerChat,
  providerKeyStatus,
  providerUsage,
  saveProfile,
  setProviderBudget,
  setProviderKey,
  setRole,
  testProvider,
} from "../lib/ipc";

type LogLevel = "info" | "success" | "error";

interface Props {
  disabled: boolean;
  onLog: (level: LogLevel, message: string) => void;
  initialProjectId?: string;
}

const ROLES: Array<{ id: RoleName; label: string }> = [
  { id: "interviewer", label: "Intervieweur" },
  { id: "modeler", label: "Modélisateur" },
  { id: "narrator", label: "Narrateur" },
  { id: "delegate", label: "Délégué" },
  { id: "coder", label: "Codeur" },
];

interface ProfileForm {
  name: string;
  provider: string;
  model: string;
  baseUrl: string;
  apiKey: string;
  keychainRef: string;
}

const EMPTY_FORM: ProfileForm = {
  name: "",
  provider: "openai",
  model: "",
  baseUrl: "",
  apiKey: "",
  keychainRef: "",
};

function formatMicros(value: number): string {
  return (value / 1_000_000).toFixed(2);
}

function newKeychainRef(): string {
  return `seefuture:${crypto.randomUUID()}`;
}

export function ProvidersPanel({ disabled, onLog, initialProjectId }: Props) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [newProjectName, setNewProjectName] = useState("");
  const [catalog, setCatalog] = useState<ProviderCatalogResult | null>(null);
  const [profiles, setProfiles] = useState<ProviderProfile[]>([]);
  const [roles, setRoles] = useState<RoleAssignment[]>([]);
  const [usage, setUsage] = useState<ProviderUsageResult | null>(null);
  const [budget, setBudget] = useState<BudgetResult | null>(null);
  const [form, setForm] = useState<ProfileForm>(EMPTY_FORM);
  const [tests, setTests] = useState<Record<string, ProviderTestResult>>({});
  const [models, setModels] = useState<Record<string, ProviderModelInfo[]>>({});
  const [roleProfiles, setRoleProfiles] = useState<Record<string, string>>({});
  const [roleModels, setRoleModels] = useState<Record<string, string>>({});
  const [budgetInput, setBudgetInput] = useState("");
  const [chatProfileId, setChatProfileId] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatResult, setChatResult] = useState<ProviderChatResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const provider = useMemo(
    () => catalog?.providers.find((item) => item.id === form.provider) ?? null,
    [catalog, form.provider],
  );

  const loadProjectData = useCallback(
    async (id: string) => {
      const [profileResult, roleResult, usageResult, budgetResult] = await Promise.all([
        listProfiles(id),
        listRoles(id),
        providerUsage(id),
        providerBudget(id),
      ]);
      setProfiles(profileResult.profiles);
      setRoles(roleResult.assignments);
      setUsage(usageResult);
      setBudget(budgetResult);
      setBudgetInput(
        budgetResult.limitMicros > 0 ? String(budgetResult.limitMicros / 1_000_000) : "",
      );
      setRoleProfiles((current) => {
        const next = { ...current };
        for (const assignment of roleResult.assignments) {
          next[assignment.role] = assignment.providerProfileId;
        }
        return next;
      });
      setRoleModels((current) => {
        const next = { ...current };
        for (const assignment of roleResult.assignments) {
          next[assignment.role] = assignment.model;
        }
        return next;
      });
      setChatProfileId((current) => {
        if (profileResult.profiles.some((item) => item.id === current)) return current;
        return profileResult.profiles[0]?.id ?? "";
      });
    },
    [],
  );

  const loadProjects = useCallback(
    async (selected?: string) => {
      const result = await listProjects();
      setProjects(result.projects);
      const next =
        selected ?? initialProjectId ?? projectId ?? result.projects[0]?.id ?? "";
      setProjectId(next);
      if (next) await loadProjectData(next);
      return result.projects;
    },
    [initialProjectId, loadProjectData, projectId],
  );

  useEffect(() => {
    if (disabled) return;
    void providerCatalog()
      .then(setCatalog)
      .catch((reason) => onLog("error", `Catalogue fournisseurs: ${String(reason)}`));
    void loadProjects(initialProjectId).catch((reason) =>
      onLog("error", `Chargement des projets: ${String(reason)}`),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disabled, initialProjectId]);

  const selectProvider = (id: string) => {
    const spec = catalog?.providers.find((item) => item.id === id) ?? null;
    setForm((current) => ({
      ...current,
      provider: id,
      model: spec?.defaultModel ?? "",
      baseUrl: spec?.baseUrl ?? "",
    }));
  };

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) {
      setError("Nom de projet requis.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await createProject(newProjectName.trim());
      setNewProjectName("");
      await loadProjects(result.project.id);
      onLog("success", `Projet « ${result.project.name} » créé.`);
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  };

  const handleSaveProfile = async () => {
    if (!projectId) return;
    if (!form.name.trim()) {
      setError("Nom du profil requis.");
      return;
    }
    if (!form.provider.trim()) {
      setError("Fournisseur requis.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const requiresKey = provider?.requiresKey ?? true;
      let keychainRef: string | null = form.keychainRef || null;
      if (form.apiKey.trim()) {
        keychainRef = keychainRef || newKeychainRef();
        await setProviderKey(keychainRef, form.apiKey.trim());
      } else if (requiresKey) {
        if (!keychainRef || !(await providerKeyStatus(keychainRef))) {
          setError("Clé API requise pour ce fournisseur.");
          return;
        }
      } else {
        keychainRef = null;
      }
      await saveProfile({
        projectId,
        name: form.name.trim(),
        provider: form.provider,
        model: form.model.trim() || null,
        baseUrl: form.baseUrl.trim() || null,
        keychainRef,
        capabilities: {},
      });
      setForm(EMPTY_FORM);
      await loadProjectData(projectId);
      onLog("success", `Profil « ${form.name.trim()} » enregistré.`);
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  };

  const handleEdit = (profile: ProviderProfile) => {
    setForm({
      name: profile.name,
      provider: profile.provider,
      model: profile.model ?? "",
      baseUrl: profile.baseUrl ?? "",
      apiKey: "",
      keychainRef: profile.keychainRef ?? "",
    });
    setError("");
  };

  const handleDeleteProfile = async (profile: ProviderProfile) => {
    if (!projectId) return;
    setBusy(true);
    setError("");
    try {
      await deleteProfile(projectId, profile.id);
      if (form.keychainRef === profile.keychainRef) setForm(EMPTY_FORM);
      await loadProjectData(projectId);
      onLog("success", `Profil « ${profile.name} » supprimé.`);
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  };

  const handleTest = async (profile: ProviderProfile) => {
    setBusy(true);
    setError("");
    try {
      const result = await testProvider(profile);
      setTests((current) => ({ ...current, [profile.id]: result }));
      onLog(
        result.ok ? "success" : "error",
        `${profile.name}: ${result.message} (${Math.round(result.latencyMs)} ms)`,
      );
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  };

  const handleModels = async (profile: ProviderProfile) => {
    setBusy(true);
    setError("");
    try {
      const result = await listProviderModels(profile);
      setModels((current) => ({ ...current, [profile.id]: result.models }));
      onLog("info", `${result.models.length} modèle(s) disponible(s) chez ${profile.name}.`);
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  };

  const handleAssignRole = async (role: RoleName) => {
    if (!projectId) return;
    const profileId = roleProfiles[role];
    const selected = profiles.find((item) => item.id === profileId);
    if (!selected) {
      setError("Choisissez un profil pour ce rôle.");
      return;
    }
    const model = roleModels[role] || selected.model || "";
    if (!model.trim()) {
      setError("Le rôle doit avoir un modèle.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await setRole(projectId, role, selected.id, model.trim());
      await loadProjectData(projectId);
      onLog("success", `Rôle ${role} assigné à « ${selected.name} ».`);
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  };

  const handleDeleteRole = async (role: RoleName) => {
    if (!projectId) return;
    setBusy(true);
    try {
      await deleteRole(projectId, role);
      await loadProjectData(projectId);
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  };

  const handleBudget = async () => {
    if (!projectId) return;
    const value = Number(budgetInput.replace(",", "."));
    if (!Number.isFinite(value) || value < 0) {
      setError("Plafond invalide.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await setProviderBudget(projectId, Math.round(value * 1_000_000));
      setBudget(result);
      await loadProjectData(projectId);
      onLog("success", `Plafond fixé à ${formatMicros(result.limitMicros)}.`);
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  };

  const handleDeleteBudget = async () => {
    if (!projectId) return;
    setBusy(true);
    try {
      await deleteProviderBudget(projectId);
      await loadProjectData(projectId);
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  };

  const handleChat = async () => {
    if (!projectId) return;
    const profile = profiles.find((item) => item.id === chatProfileId);
    if (!profile) {
      setError("Choisissez un profil pour la conversation.");
      return;
    }
    if (!chatInput.trim()) {
      setError("Message vide.");
      return;
    }
    setBusy(true);
    setError("");
    setChatResult(null);
    try {
      const result = await providerChat({
        projectId,
        profile,
        request: {
          model: profile.model ?? form.model ?? "",
          messages: [{ role: "user", content: chatInput.trim() }],
          maxTokens: 2048,
        },
      });
      setChatResult(result);
      setChatInput("");
      await loadProjectData(projectId);
      onLog("success", `Réponse reçue de ${result.provider}.`);
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  };

  if (disabled) {
    return (
      <section className="card card--wide">
        <h2>Fournisseurs IA</h2>
        <p className="hint">Disponible uniquement dans l'application Tauri.</p>
      </section>
    );
  }

  return (
    <div className="providers">
      <section className="card card--wide">
        <h2>Projet</h2>
        <div className="form-row">
          <label>
            Projet actif
            <select
              value={projectId}
              onChange={(event) => {
                setProjectId(event.target.value);
                void loadProjectData(event.target.value);
              }}
            >
              {projects.length === 0 ? <option value="">Aucun projet</option> : null}
              {projects.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Nouveau projet
            <input
              value={newProjectName}
              onChange={(event) => setNewProjectName(event.target.value)}
              placeholder="Nom du projet"
            />
          </label>
          <button type="button" onClick={handleCreateProject} disabled={busy}>
            Créer
          </button>
        </div>
      </section>

      {error ? <p className="error">{error}</p> : null}

      {projectId ? (
        <>
          <section className="card card--wide">
            <h2>Profil fournisseur</h2>
            <div className="form-grid">
              <label>
                Fournisseur
                <select value={form.provider} onChange={(event) => selectProvider(event.target.value)}>
                  {(catalog?.providers ?? []).map((item: ProviderCatalogEntry) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                      {item.requiresKey ? "" : " (sans clé)"}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Nom
                <input
                  value={form.name}
                  onChange={(event) => setForm({ ...form, name: event.target.value })}
                  placeholder="Ex. OpenAI rapide"
                />
              </label>
              <label>
                Modèle
                <input
                  value={form.model}
                  onChange={(event) => setForm({ ...form, model: event.target.value })}
                  placeholder={provider?.defaultModel ?? "gpt-4o-mini"}
                />
              </label>
              <label>
                URL de base
                <input
                  value={form.baseUrl}
                  onChange={(event) => setForm({ ...form, baseUrl: event.target.value })}
                  placeholder="https://..."
                />
              </label>
              <label className="form-span">
                Clé API
                <input
                  type="password"
                  autoComplete="off"
                  value={form.apiKey}
                  onChange={(event) => setForm({ ...form, apiKey: event.target.value })}
                  placeholder={
                    form.keychainRef ? "Laisser vide pour conserver la clé" : "Stockée dans le trousseau"
                  }
                />
                <span className="field-hint">
                  Jamais en base ni dans les logs. Référence : {form.keychainRef || "nouvelle"}
                </span>
              </label>
            </div>
            <div className="actions">
              <button type="button" onClick={handleSaveProfile} disabled={busy}>
                {form.keychainRef ? "Mettre à jour" : "Enregistrer"}
              </button>
              {form.keychainRef ? (
                <button
                  type="button"
                  className="button--secondary"
                  onClick={() => setForm(EMPTY_FORM)}
                  disabled={busy}
                >
                  Annuler
                </button>
              ) : null}
            </div>
            <p className="hint">
              Les capacités et prix sont lus dans la matrice versionnée{" "}
              {catalog?.capabilitiesVersion ?? "locale"}.
            </p>
          </section>

          <section className="card card--wide">
            <h2>Profils enregistrés</h2>
            {profiles.length === 0 ? (
              <p className="hint">Aucun profil.</p>
            ) : (
              <ul className="list">
                {profiles.map((item) => (
                  <li key={item.id}>
                    <div>
                      <strong>{item.name}</strong>
                      <span className="muted">
                        {item.provider} · {item.model ?? "modèle par défaut"}
                      </span>
                      {tests[item.id] ? (
                        <span className={tests[item.id].ok ? "ok" : "error-inline"}>
                          {tests[item.id].message}
                        </span>
                      ) : null}
                      {models[item.id] ? (
                        <span className="muted">
                          {models[item.id]
                            .slice(0, 8)
                            .map((model) => model.id)
                            .join(", ")}
                          {models[item.id].length > 8 ? "…" : ""}
                        </span>
                      ) : null}
                    </div>
                    <div className="actions">
                      <button
                        type="button"
                        className="button--secondary"
                        onClick={() => handleTest(item)}
                        disabled={busy}
                      >
                        Tester
                      </button>
                      <button
                        type="button"
                        className="button--ghost"
                        onClick={() => handleModels(item)}
                        disabled={busy}
                      >
                        Modèles
                      </button>
                      <button
                        type="button"
                        className="button--ghost"
                        onClick={() => handleEdit(item)}
                        disabled={busy}
                      >
                        Modifier
                      </button>
                      <button
                        type="button"
                        className="button--danger"
                        onClick={() => handleDeleteProfile(item)}
                        disabled={busy}
                      >
                        Supprimer
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="card card--wide">
            <h2>Rôles</h2>
            <div className="role-list">
              {ROLES.map((role) => {
                const assignment = roles.find((item) => item.role === role.id);
                return (
                  <div className="role-row" key={role.id}>
                    <div className="role-name">
                      <strong>{role.label}</strong>
                      <span className="muted">{role.id}</span>
                    </div>
                    <select
                      value={roleProfiles[role.id] ?? ""}
                      onChange={(event) => {
                        const profileId = event.target.value;
                        const nextProfile = profiles.find((item) => item.id === profileId);
                        setRoleProfiles({ ...roleProfiles, [role.id]: profileId });
                        setRoleModels({
                          ...roleModels,
                          [role.id]: nextProfile?.model ?? "",
                        });
                      }}
                    >
                      <option value="">—</option>
                      {profiles.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                    <input
                      value={roleModels[role.id] ?? ""}
                      onChange={(event) =>
                        setRoleModels({ ...roleModels, [role.id]: event.target.value })
                      }
                      placeholder={profiles.find((item) => item.id === roleProfiles[role.id])?.model ?? "modèle"}
                    />
                    <button
                      type="button"
                      className="button--secondary"
                      onClick={() => handleAssignRole(role.id)}
                      disabled={busy}
                    >
                      Assigner
                    </button>
                    {assignment ? (
                      <button
                        type="button"
                        className="button--ghost"
                        onClick={() => handleDeleteRole(role.id)}
                        disabled={busy}
                      >
                        Retirer
                      </button>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </section>

          <section className="card">
            <h2>Budget</h2>
            <dl className="facts">
              <div>
                <dt>Plafond</dt>
                <dd>{budget ? formatMicros(budget.limitMicros) : "illimité"}</dd>
              </div>
              <div>
                <dt>Dépensé</dt>
                <dd>{formatMicros(budget?.spentMicros ?? 0)}</dd>
              </div>
              <div>
                <dt>Entrées</dt>
                <dd>{usage?.entries.length ?? 0}</dd>
              </div>
              <div>
                <dt>Tokens</dt>
                <dd>
                  {usage?.inputTokens ?? 0} / {usage?.outputTokens ?? 0}
                </dd>
              </div>
            </dl>
            {budget && budget.limitMicros > 0 && budget.spentMicros / budget.limitMicros >= 0.8 ? (
              <p className="error-inline">
                Alerte : {Math.round((budget.spentMicros / budget.limitMicros) * 100)} % du plafond
                consommé.
              </p>
            ) : null}
            <div className="form-row budget-row">
              <label>
                Plafond (USD)
                <input
                  value={budgetInput}
                  onChange={(event) => setBudgetInput(event.target.value)}
                  inputMode="decimal"
                  placeholder="0 = illimité"
                />
              </label>
              <button type="button" onClick={handleBudget} disabled={busy}>
                Appliquer
              </button>
              <button
                type="button"
                className="button--ghost"
                onClick={handleDeleteBudget}
                disabled={busy}
              >
                Retirer
              </button>
            </div>
            <p className="hint">
              Alerte et blocage avant l'appel si le coût estimé dépasse le plafond.
            </p>
          </section>

          <section className="card">
            <h2>Conversation de test</h2>
            <label>
              Profil
              <select
                value={chatProfileId}
                onChange={(event) => setChatProfileId(event.target.value)}
              >
                {profiles.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Message
              <textarea
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                rows={4}
                placeholder="Décrivez le projet…"
              />
            </label>
            <button type="button" onClick={handleChat} disabled={busy || profiles.length === 0}>
              Envoyer
            </button>
            {chatResult ? (
              <div className="chat-result">
                <p>{chatResult.text}</p>
                <span className="muted">
                  {chatResult.provider} · {chatResult.model} · {chatResult.usage.totalTokens} tokens ·{" "}
                  {formatMicros(chatResult.usage.costMicros)} USD
                </span>
                {chatResult.fallbacks && chatResult.fallbacks.length > 0 ? (
                  <p className="error-inline">
                    Repli :{" "}
                    {chatResult.fallbacks
                      .map((item) => `${item.provider} (${item.reason})`)
                      .join(", ")}
                  </p>
                ) : null}
              </div>
            ) : null}
          </section>
        </>
      ) : null}
    </div>
  );
}
