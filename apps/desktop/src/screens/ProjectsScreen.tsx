import type { Project } from "@see/protocol";
import { Badge, Button, Card, CardHeader, EmptyState, Field, InlineAlert, Stat } from "@see/ui";
import { useState } from "react";
import { formatDateTime } from "../lib/format";

interface Props {
  projects: Project[];
  activeProject: Project | null;
  busy: boolean;
  error: string;
  onCreate: (name: string, description: string) => Promise<boolean>;
  onOpen: (project: Project) => void;
  onRefresh: () => void;
}

export function ProjectsScreen({
  projects,
  activeProject,
  busy,
  error,
  onCreate,
  onOpen,
  onRefresh,
}: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const submit = async () => {
    if (!name.trim()) return;
    const created = await onCreate(name.trim(), description.trim());
    if (!created) return;
    setName("");
    setDescription("");
  };

  return (
    <div className="screen">
      <div className="screen__heading">
        <div>
          <p className="ui-eyebrow">Espace de travail</p>
          <h1>Vos projets</h1>
          <p className="ui-muted">
            Chaque projet garde son brief, ses hypothèses, ses simulations et sa trace locale.
          </p>
        </div>
        <Button variant="secondary" onClick={onRefresh} disabled={busy}>
          Actualiser
        </Button>
      </div>

      {error ? <InlineAlert tone="danger">{error}</InlineAlert> : null}

      {projects.length === 0 ? (
        <Card>
          <CardHeader
            eyebrow="Premier pas"
            title="Bienvenue dans See The Future"
            description="Transformez une idée en scénario chiffré, sans inventer de chiffres."
          />
          <div className="onboarding-grid">
            <div>
              <strong>1. Décrivez votre idée</strong>
              <p>L'entretien guidé complète un brief structuré champ par champ.</p>
            </div>
            <div>
              <strong>2. Fixez vos hypothèses</strong>
              <p>Prix, coûts, demande : chaque valeur a une source et une incertitude.</p>
            </div>
            <div>
              <strong>3. Lisez les résultats</strong>
              <p>Le moteur calcule. L'IA raconte, sans jamais produire un chiffre.</p>
            </div>
          </div>
          <InlineAlert tone="neutral" title="Vos clés restent chez vous">
            Bring your own key : les clés API vont dans le trousseau du système, jamais dans la base.
            Ollama reste disponible pour un usage 100 % hors ligne.
          </InlineAlert>
          <EmptyState
            title="Aucun projet pour l'instant"
            description="Créez un projet ci-dessous pour démarrer le parcours complet."
          />
        </Card>
      ) : null}

      <div className="split">
        <Card>
          <CardHeader
            eyebrow="Nouveau"
            title="Créer un projet"
            description="Un nom suffit. Vous pourrez tout modifier ensuite."
          />
          <div className="ui-field-grid">
            <Field
              label="Nom du projet"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Ex. Dépôt de boissons à Abidjan"
              hint="Visible dans la liste des projets."
            />
            <Field
              label="Description (optionnel)"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Une phrase pour retrouver le projet"
            />
          </div>
          <div className="ui-actions">
            <Button onClick={submit} disabled={busy || !name.trim()}>
              Créer le projet
            </Button>
          </div>
        </Card>

        <Card>
          <CardHeader eyebrow="Repère" title="Projet actif" />
          {activeProject ? (
            <div className="ui-stack">
              <Stat label="Nom" value={activeProject.name} />
              <Stat label="Devise" value={activeProject.currency} hint="FCFA par défaut" />
              <Stat label="Dernière ouverture" value={formatDateTime(activeProject.updatedAt)} />
              <Button variant="secondary" onClick={() => onOpen(activeProject)} disabled={busy}>
                Continuer ce projet
              </Button>
            </div>
          ) : (
            <p className="ui-muted">Sélectionnez un projet dans la liste.</p>
          )}
        </Card>
      </div>

      <Card>
        <CardHeader
          eyebrow="Bibliothèque"
          title="Projets récents"
          description={`${projects.length} projet${projects.length > 1 ? "s" : ""} sur cet appareil.`}
        />
        {projects.length === 0 ? (
          <p className="ui-muted">Aucun projet enregistré.</p>
        ) : (
          <ul className="project-list">
            {projects.map((project) => (
              <li key={project.id} className={project.id === activeProject?.id ? "project-list__item project-list__item--active" : "project-list__item"}>
                <div>
                  <div className="project-list__title">
                    <strong>{project.name}</strong>
                    {project.id === activeProject?.id ? <Badge tone="accent">Actif</Badge> : null}
                    <Badge tone={project.status === "active" ? "ok" : "warn"}>{project.status}</Badge>
                  </div>
                  <p>{project.description || "Sans description"}</p>
                  <span className="ui-muted">
                    {project.currency} · modifié le {formatDateTime(project.updatedAt)}
                  </span>
                </div>
                <Button variant="secondary" onClick={() => onOpen(project)} disabled={busy}>
                  Ouvrir
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
