import type { BriefRecord, Project } from "@see/protocol";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  InlineAlert,
  TextareaField,
} from "@see/ui";
import { useEffect, useMemo, useState } from "react";

interface Props {
  project: Project;
  brief: BriefRecord | null;
  busy: boolean;
  error: string;
  onSave: (content: Record<string, unknown>, status: "draft" | "validated") => Promise<void>;
  onNext: () => void;
}

const REQUIRED = [
  ["problem", "Problème"],
  ["customer", "Client cible"],
  ["valueProposition", "Proposition de valeur"],
  ["revenueModel", "Modèle de revenus"],
  ["costStructure", "Structure de coûts"],
  ["geography", "Zone géographique"],
] as const;

const OPTIONAL = [
  ["competitors", "Concurrents"],
  ["constraints", "Contraintes"],
  ["notes", "Notes libres"],
] as const;

interface BriefForm {
  problem: string;
  customer: string;
  valueProposition: string;
  revenueModel: string;
  costStructure: string;
  geography: string;
  competitors: string;
  constraints: string;
  notes: string;
  keyAssumptions: string;
  currency: string;
  horizonMonths: string;
}

const EMPTY: BriefForm = {
  problem: "",
  customer: "",
  valueProposition: "",
  revenueModel: "",
  costStructure: "",
  geography: "",
  competitors: "",
  constraints: "",
  notes: "",
  keyAssumptions: "",
  currency: "XOF",
  horizonMonths: "12",
};

function fromRecord(record: BriefRecord | null, project: Project): BriefForm {
  const content = record?.content ?? {};
  const text = (key: string): string => {
    const value = content[key];
    return typeof value === "string" ? value : "";
  };
  const assumptions = Array.isArray(content.keyAssumptions)
    ? content.keyAssumptions.filter((item): item is string => typeof item === "string").join("\n")
    : "";
  return {
    ...EMPTY,
    problem: text("problem"),
    customer: text("customer"),
    valueProposition: text("valueProposition"),
    revenueModel: text("revenueModel"),
    costStructure: text("costStructure"),
    geography: text("geography"),
    competitors: text("competitors"),
    constraints: text("constraints"),
    notes: text("notes"),
    keyAssumptions: assumptions,
    currency: text("currency") || project.currency || "XOF",
    horizonMonths: String(content.horizonMonths ?? 12),
  };
}

export function BriefScreen({ project, brief, busy, error, onSave, onNext }: Props) {
  const [form, setForm] = useState<BriefForm>(() => fromRecord(brief, project));

  useEffect(() => {
    setForm(fromRecord(brief, project));
  }, [brief, project]);

  const missing = useMemo(
    () => REQUIRED.filter(([key]) => !form[key].trim()).map(([, label]) => label),
    [form],
  );

  const update = (key: keyof BriefForm, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const payload = (): Record<string, unknown> => {
    const currency = form.currency.trim().toUpperCase();
    const content: Record<string, unknown> = {
      problem: form.problem.trim(),
      customer: form.customer.trim(),
      valueProposition: form.valueProposition.trim(),
      revenueModel: form.revenueModel.trim(),
      costStructure: form.costStructure.trim(),
      geography: form.geography.trim(),
      currency: /^[A-Z]{3}$/.test(currency) ? currency : project.currency,
      horizonMonths: Number(form.horizonMonths) || 12,
      keyAssumptions: form.keyAssumptions
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean),
    };
    for (const [key] of OPTIONAL) {
      if (form[key].trim()) content[key] = form[key].trim();
    }
    return content;
  };

  const save = async (status: "draft" | "validated") => {
    await onSave(payload(), status);
  };

  const canValidate = missing.length === 0;

  return (
    <div className="screen">
      <div className="screen__heading">
        <div>
          <p className="ui-eyebrow">Cadrage</p>
          <h1>Brief du projet</h1>
          <p className="ui-muted">
            Les six champs requis structurent le scénario. Le reste enrichit le contexte.
          </p>
        </div>
        <div className="ui-actions">
          <Badge tone={brief?.status === "validated" ? "ok" : "warn"}>
            {brief?.status === "validated" ? "Validé" : brief ? "Brouillon" : "Vide"}
          </Badge>
          {brief ? <Badge>version {brief.version}</Badge> : null}
        </div>
      </div>

      {error ? <InlineAlert tone="danger" title="Action impossible">{error}</InlineAlert> : null}
      {missing.length > 0 ? (
        <InlineAlert tone="warn" title="Champs requis manquants">
          {missing.join(", ")}
        </InlineAlert>
      ) : null}

      <div className="split split--wide">
        <Card>
          <CardHeader eyebrow="Requis" title="Le cœur du projet" />
          <div className="ui-field-grid">
            <TextareaField
              label="Problème"
              value={form.problem}
              onChange={(value) => update("problem", value)}
              placeholder="Quel problème concret le client veut-il résoudre ?"
            />
            <TextareaField
              label="Client cible"
              value={form.customer}
              onChange={(value) => update("customer", value)}
              placeholder="Qui paie, où, à quelle fréquence ?"
            />
            <TextareaField
              label="Proposition de valeur"
              value={form.valueProposition}
              onChange={(value) => update("valueProposition", value)}
              placeholder="Pourquoi choisir cette offre plutôt qu'une autre ?"
            />
            <TextareaField
              label="Modèle de revenus"
              value={form.revenueModel}
              onChange={(value) => update("revenueModel", value)}
              placeholder="Prix de vente, marge, abonnement, commissions…"
            />
            <TextareaField
              label="Structure de coûts"
              value={form.costStructure}
              onChange={(value) => update("costStructure", value)}
              placeholder="Achats, loyer, salaires, logistique…"
            />
            <Field
              label="Zone géographique"
              value={form.geography}
              onChange={(event) => update("geography", event.target.value)}
              placeholder="Ex. Abidjan, Côte d'Ivoire"
            />
          </div>
        </Card>

        <Card>
          <CardHeader eyebrow="Contexte" title="Précisions utiles" />
          <div className="ui-field-grid">
            {OPTIONAL.map(([key, label]) => (
              <Field
                key={key}
                label={label}
                value={form[key]}
                onChange={(event) => update(key, event.target.value)}
              />
            ))}
            <TextareaField
              label="Hypothèses clés"
              value={form.keyAssumptions}
              onChange={(value) => update("keyAssumptions", value)}
              rows={5}
              hint="Une hypothèse par ligne."
              placeholder="Ex. Demande stable toute l'année"
            />
            <div className="inline-fields">
              <Field
                label="Devise"
                value={form.currency}
                onChange={(event) => update("currency", event.target.value.toUpperCase())}
                hint="Code ISO à 3 lettres, XOF par défaut"
              />
              <Field
                label="Horizon (mois)"
                type="number"
                min={1}
                max={120}
                value={form.horizonMonths}
                onChange={(event) => update("horizonMonths", event.target.value)}
              />
            </div>
          </div>
        </Card>
      </div>

      <Card>
        <div className="ui-actions ui-actions--end">
          <Button variant="secondary" onClick={() => void save("draft")} disabled={busy}>
            Enregistrer le brouillon
          </Button>
          <Button onClick={() => void save("validated")} disabled={busy || !canValidate}>
            Valider le brief
          </Button>
          <Button
            variant="ghost"
            onClick={onNext}
            disabled={brief?.status !== "validated"}
          >
            Passer aux hypothèses
          </Button>
        </div>
      </Card>
    </div>
  );
}
