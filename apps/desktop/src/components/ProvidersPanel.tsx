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
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  InlineAlert,
  SelectField,
  Table,
  TextareaField,
} from "@see/ui";
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
      <Card className="card--wide">
        <CardHeader
          eyebrow="Fournisseurs IA"
          title="Configuration indisponible"
        />
        <p className="ui-muted">Disponible uniquement dans l'application Tauri.</p>
      </Card>
    );
  }

  return (
    <div className="providers">
      <Card className="card--wide">
        <CardHeader eyebrow="Projet" title="Contexte de travail" />
        <div className="ui-field-grid">
          <SelectField
            label="Projet actif"
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
          </SelectField>
          <Field
            label="Nouveau projet"
            value={newProjectName}
            onChange={(event) => setNewProjectName(event.target.value)}
            placeholder="Nom du projet"
          />
        </div>
        <div className="ui-actions">
          <Button onClick={handleCreateProject} disabled={busy}>
            Créer
          </Button>
        </div>
      </Card>

      {error ? <InlineAlert tone="danger" title="Action impossible">{error}</InlineAlert> : null}

      {projectId ? (
        <>
          <Card className="card--wide">
            <CardHeader eyebrow="Profil" title="Profil fournisseur" />
            <div className="ui-field-grid">
              <SelectField
                label="Fournisseur"
                value={form.provider}
                onChange={(event) => selectProvider(event.target.value)}
              >
                {(catalog?.providers ?? []).map((item: ProviderCatalogEntry) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                    {item.requiresKey ? "" : " (sans clé)"}
                  </option>
                ))}
              </SelectField>
              <Field
                label="Nom"
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                placeholder="Ex. OpenAI rapide"
              />
              <Field
                label="Modèle"
                value={form.model}
                onChange={(event) => setForm({ ...form, model: event.target.value })}
                placeholder={provider?.defaultModel ?? "gpt-4o-mini"}
              />
              <Field
                label="URL de base"
                value={form.baseUrl}
                onChange={(event) => setForm({ ...form, baseUrl: event.target.value })}
                placeholder="https://..."
              />
              <div className="ui-field-grid__span">
                <Field
                  label="Clé API"
                  type="password"
                  autoComplete="off"
                  value={form.apiKey}
                  onChange={(event) => setForm({ ...form, apiKey: event.target.value })}
                  placeholder={
                    form.keychainRef ? "Laisser vide pour conserver la clé" : "Stockée dans le trousseau"
                  }
                  hint={`Jamais en base ni dans les logs. Référence : ${form.keychainRef || "nouvelle"}`}
                />
              </div>
            </div>
            <div className="ui-actions">
              <Button onClick={handleSaveProfile} disabled={busy}>
                {form.keychainRef ? "Mettre à jour" : "Enregistrer"}
              </Button>
              {form.keychainRef ? (
                <Button variant="secondary" onClick={() => setForm(EMPTY_FORM)} disabled={busy}>
                  Annuler
                </Button>
              ) : null}
            </div>
            <p className="ui-muted">
              Les capacités et prix sont lus dans la matrice versionnée{" "}
              {catalog?.capabilitiesVersion ?? "locale"}.
            </p>
          </Card>

          <Card className="card--wide">
            <CardHeader eyebrow="Profils" title="Profils enregistrés" />
            {profiles.length === 0 ? (
              <p className="ui-muted">Aucun profil. Créez-en un ci-dessus pour assigner les rôles.</p>
            ) : (
              <ul className="list">
                {profiles.map((item) => (
                  <li key={item.id}>
                    <div>
                      <strong>{item.name}</strong>
                      <span className="ui-muted">
                        {item.provider} · {item.model ?? "modèle par défaut"}
                      </span>
                      {tests[item.id] ? (
                        <Badge tone={tests[item.id].ok ? "ok" : "danger"}>{tests[item.id].message}</Badge>
                      ) : null}
                      {models[item.id] ? (
                        <span className="ui-muted">
                          {models[item.id]
                            .slice(0, 8)
                            .map((model) => model.id)
                            .join(", ")}
                          {models[item.id].length > 8 ? "…" : ""}
                        </span>
                      ) : null}
                    </div>
                    <div className="ui-actions">
                      <Button variant="secondary" size="small" onClick={() => handleTest(item)} disabled={busy}>
                        Tester
                      </Button>
                      <Button variant="ghost" size="small" onClick={() => handleModels(item)} disabled={busy}>
                        Modèles
                      </Button>
                      <Button variant="ghost" size="small" onClick={() => handleEdit(item)} disabled={busy}>
                        Modifier
                      </Button>
                      <Button variant="danger" size="small" onClick={() => handleDeleteProfile(item)} disabled={busy}>
                        Supprimer
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card className="card--wide">
            <CardHeader eyebrow="Rôles" title="Assignation des agents" />
            <div className="role-list">
              {ROLES.map((role) => {
                const assignment = roles.find((item) => item.role === role.id);
                return (
                  <div className="role-row" key={role.id}>
                    <div className="role-name">
                      <strong>{role.label}</strong>
                      <span className="ui-muted">{role.id}</span>
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
                    <Button variant="secondary" size="small" onClick={() => handleAssignRole(role.id)} disabled={busy}>
                      Assigner
                    </Button>
                    {assignment ? (
                      <Button variant="ghost" size="small" onClick={() => handleDeleteRole(role.id)} disabled={busy}>
                        Retirer
                      </Button>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </Card>

          <Card>
            <CardHeader eyebrow="Budget" title="Plafond de dépense" />
            <Table
              columns={[
                { key: "measure", header: "Mesure" },
                { key: "value", header: "Valeur", mono: true },
              ]}
              rows={[
                { measure: "Plafond", value: budget ? `${formatMicros(budget.limitMicros)} USD` : "illimité" },
                { measure: "Dépensé", value: `${formatMicros(budget?.spentMicros ?? 0)} USD` },
                { measure: "Entrées", value: String(usage?.entries.length ?? 0) },
                { measure: "Tokens", value: `${usage?.inputTokens ?? 0} / ${usage?.outputTokens ?? 0}` },
              ]}
              rowKey={(row) => row.measure}
            />
            {budget && budget.limitMicros > 0 && budget.spentMicros / budget.limitMicros >= 0.8 ? (
              <InlineAlert tone="warn" title="Plafond presque atteint">
                {Math.round((budget.spentMicros / budget.limitMicros) * 100)} % du plafond consommé. Le
                blocage survient avant l'appel si le coût estimé dépasse le plafond.
              </InlineAlert>
            ) : null}
            <div className="ui-actions">
              <Field
                label="Plafond (USD)"
                value={budgetInput}
                onChange={(event) => setBudgetInput(event.target.value)}
                inputMode="decimal"
                placeholder="0 = illimité"
              />
              <Button onClick={handleBudget} disabled={busy}>
                Appliquer
              </Button>
              <Button variant="ghost" onClick={handleDeleteBudget} disabled={busy}>
                Retirer
              </Button>
            </div>
          </Card>

          <Card>
            <CardHeader eyebrow="Diagnostic" title="Conversation de test" />
            <div className="ui-field-grid">
              <SelectField
                label="Profil"
                value={chatProfileId}
                onChange={(event) => setChatProfileId(event.target.value)}
              >
                {profiles.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </SelectField>
              <div className="ui-field-grid__span">
                <TextareaField
                  label="Message"
                  value={chatInput}
                  onChange={setChatInput}
                  rows={4}
                  placeholder="Décrivez le projet…"
                />
              </div>
            </div>
            <div className="ui-actions">
              <Button onClick={handleChat} disabled={busy || profiles.length === 0}>
                Envoyer
              </Button>
            </div>
            {chatResult ? (
              <div className="chat-result">
                <p>{chatResult.text}</p>
                <span className="ui-muted">
                  {chatResult.provider} · {chatResult.model} · {chatResult.usage.totalTokens} tokens ·{" "}
                  {formatMicros(chatResult.usage.costMicros)} USD
                </span>
                {chatResult.fallbacks && chatResult.fallbacks.length > 0 ? (
                  <InlineAlert tone="warn" title="Repli utilisé">
                    {chatResult.fallbacks
                      .map((item) => `${item.provider} (${item.reason})`)
                      .join(", ")}
                  </InlineAlert>
                ) : null}
              </div>
            ) : null}
          </Card>
        </>
      ) : null}
    </div>
  );
}
