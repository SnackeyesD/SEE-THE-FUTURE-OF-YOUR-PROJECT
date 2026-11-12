/**
 * Vitrine des primitives « Ink & Signal » (refont phase 03).
 * Visible en dev : http://localhost:5173/?showcase
 * Chaque primitive y est montrée dans tous ses états. Zéro hex.
 */
import {
  Badge,
  Button,
  Card,
  CardHeader,
  DivergingBars,
  EmptyState,
  Field,
  Histogram,
  InlineAlert,
  LineChart,
  ProgressBar,
  SelectField,
  SERIES,
  Sparkline,
  Stat,
  Table,
  Tabs,
  TextareaField,
  type TableColumn,
} from "@see/ui";
import { useState } from "react";

const sectionStyle: React.CSSProperties = {
  padding: "var(--sp-5)",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-4)",
  background: "var(--bg-surface)",
  display: "grid",
  gap: "var(--sp-3)",
};

const h2Style: React.CSSProperties = {
  margin: 0,
  fontSize: "var(--fs-13)",
  color: "var(--muted)",
  textTransform: "uppercase",
  letterSpacing: "0.08em",
};

type ScenarioRow = { name: string; p50: string; p10: string; risk: "faible" | "moyen" | "élevé" };

const scenarioRows: ScenarioRow[] = [
  { name: "Référence", p50: "245 000", p10: "-80 000", risk: "moyen" },
  { name: "Optimiste", p50: "480 000", p10: "95 000", risk: "faible" },
  { name: "Pessimiste", p50: "60 000", p10: "-210 000", risk: "élevé" },
];

/* Données de démonstration dataviz (phase 04) — agrégées comme le moteur. */
const fmtFcfa = (value: number) =>
  new Intl.NumberFormat("fr-FR", { style: "currency", currency: "XOF", maximumFractionDigits: 0, notation: "compact" }).format(value);

const scenarioLines = [0, 1, 2].map((seriesIndex) => {
  const names = ["Référence", "Optimiste", "Pessimiste"];
  const slopes = [24_500, 40_000, 5_000];
  const starts = [-80_000, 95_000, -210_000];
  return {
    id: names[seriesIndex],
    label: names[seriesIndex],
    seriesIndex,
    points: Array.from({ length: 12 }, (_, index) => ({
      x: index + 1,
      y: starts[seriesIndex] + slopes[seriesIndex] * index,
    })),
  };
});

const demoBins = Array.from({ length: 34 }, (_, index) => {
  const lower = -300_000 + index * 20_000;
  const center = 240_000;
  const spread = Math.abs((lower + 10_000 - center) / 320_000);
  const count = Math.round(240 * Math.exp(-spread * spread * 3.2));
  return { lower, upper: lower + 20_000, count: count + 2, probability: (count + 2) / 8_000 };
});

const demoPercentiles = [
  { label: "P10", value: -80_000 },
  { label: "P50", value: 245_000 },
  { label: "P90", value: 690_000 },
];

const demoTornado = [
  { label: "Prix moyen", value: 380_000 },
  { label: "Volume mensuel", value: -265_000 },
  { label: "Coût d'achat unitaire", value: -190_000 },
  { label: "Charges fixes", value: -95_000 },
  { label: "Taux de marge", value: 64_000 },
  { label: "Stock initial", value: 38_000 },
];

const sparkValues = [120, 180, 160, 240, 210, 320, 290, 410];

const scenarioColumns: Array<TableColumn<ScenarioRow>> = [
  { key: "name", header: "Scénario" },
  { key: "p50", header: "P50 (FCFA)", mono: true },
  { key: "p10", header: "P10 (FCFA)", mono: true },
  {
    key: "risk",
    header: "Risque",
    render: (row) => (
      <Badge tone={row.risk === "faible" ? "ok" : row.risk === "élevé" ? "danger" : "warn"}>
        {row.risk}
      </Badge>
    ),
  },
];

const TAB_ITEMS = [
  { id: "vue", label: "Vue" },
  { id: "saisie", label: "Saisie" },
  { id: "export", label: "Export" },
];

export function ComponentsShowcase() {
  const [tab, setTab] = useState("vue");
  const [text, setText] = useState("");

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--bg-root)",
        backgroundImage: "var(--trame)",
        backgroundSize: "var(--trame-background-size)",
        color: "var(--text)",
        fontFamily: "var(--font-ui)",
        padding: "var(--sp-6)",
        display: "grid",
        gap: "var(--sp-5)",
        maxWidth: 1180,
        margin: "0 auto",
      }}
    >
      <header>
        <p style={{ margin: 0, color: "var(--accent)", fontSize: "var(--fs-12)", fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase" }}>
          Refont · phases 03–04
        </p>
        <h1 style={{ margin: "4px 0 0", fontSize: "var(--fs-30)", letterSpacing: "-0.02em" }}>
          Vitrine des primitives & dataviz
        </h1>
        <p style={{ margin: "8px 0 0", color: "var(--muted)", fontSize: "var(--fs-14)" }}>
          Chaque composant, tous ses états. Styles : <code>packages/ui/src/primitives.css</code> + <code>packages/ui/src/viz/chart.css</code> — tokens uniquement.
        </p>
      </header>

      <section style={sectionStyle}>
        <h2 style={h2Style}>Card + CardHeader — surface standard</h2>
        <Card>
          <CardHeader
            eyebrow="Diagnostic"
            title="Runtime local"
            description="Le shell Rust supervise le sidecar Python (JSON-RPC sur stdio)."
            action={<Button variant="ghost" size="small">Recharger</Button>}
          />
          <p style={{ margin: 0, color: "var(--muted)", fontSize: "var(--fs-13)" }}>
            La carte n'ajoute jamais de couleur de décoration : fond = --bg-surface, bordure = --border.
          </p>
        </Card>
      </section>

      <section style={sectionStyle}>
        <h2 style={h2Style}>Button — 4 variants × 2 tailles + désactivé</h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--sp-3)", alignItems: "center" }}>
          <Button>Primaire</Button>
          <Button variant="secondary">Secondaire</Button>
          <Button variant="ghost">Fantôme</Button>
          <Button variant="danger">Destructif</Button>
          <Button size="small">Petit</Button>
          <Button disabled>Désactivé</Button>
        </div>
        <p style={{ margin: 0, color: "var(--faint)", fontSize: "var(--fs-12)" }}>
          Naviguez au clavier (Tab) : le focus visible est tokenisé (--focus).
        </p>
      </section>

      <section style={sectionStyle}>
        <h2 style={h2Style}>Badge — 5 tons</h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--sp-2)" }}>
          <Badge>Neutre</Badge>
          <Badge tone="ok">Sidecar actif</Badge>
          <Badge tone="warn">Révision requise</Badge>
          <Badge tone="danger">Clé invalide</Badge>
          <Badge tone="accent">protocol 1.7.0</Badge>
        </div>
      </section>

      <section style={sectionStyle}>
        <h2 style={h2Style}>Alert — titre obligatoire + action (principe Snyk)</h2>
        <div style={{ display: "grid", gap: "var(--sp-3)" }}>
          <InlineAlert tone="danger" title="Clé API refusée" action={{ label: "Ouvrir les réglages", onClick: () => undefined }}>
            Le fournisseur a répondu 401. Vérifiez la clé dans le trousseau, puis relancez le test de connexion.
          </InlineAlert>
          <InlineAlert tone="warn" title="Champs requis manquants">
            Prix moyen et stock initial sont requis avant de lancer une simulation.
          </InlineAlert>
          <InlineAlert tone="ok" title="Cohérence vérifiée">
            Aucun chiffre de la narration ne contredit la simulation.
          </InlineAlert>
          <InlineAlert tone="neutral" title="Fonctionne hors ligne">
            Avec Ollama, aucun cloud n'est requis pour simuler.
          </InlineAlert>
        </div>
      </section>

      <section style={sectionStyle}>
        <h2 style={h2Style}>Field / SelectField / TextareaField</h2>
        <div className="ui-field-grid" style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "var(--sp-4)" }}>
          <Field label="Nom du projet" placeholder="Ex. Dépôt de boissons" hint="Visible dans la liste des projets." />
          <Field label="Prix moyen" error="Obligatoire : le moteur ne peut pas simuler sans prix." />
          <SelectField label="Fournisseur" hint="La clé reste dans le trousseau OS.">
            <option>OpenAI</option>
            <option>Anthropic</option>
            <option>Ollama (local)</option>
          </SelectField>
          <TextareaField label="Idée en une phrase" value={text} onChange={setText} rows={2} />
        </div>
      </section>

      <section style={sectionStyle}>
        <h2 style={h2Style}>Stat — valeurs mono tabulaires (R4)</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--sp-3)" }}>
          <Stat label="P50" value="245 000" hint="FCFA, 10 000 runs" />
          <Stat label="P10–P90" value="-80 000 → 690 000" />
          <Stat label="P(Perte)" value="22,4 %" tone="danger" hint="runs sous 0" />
        </div>
      </section>

      <section style={sectionStyle}>
        <h2 style={h2Style}>Table — en-têtes mono, chiffres tabulaires, badges</h2>
        <Table columns={scenarioColumns} rows={scenarioRows} rowKey={(row) => row.name} />
        <Table columns={scenarioColumns} rows={[]} rowKey={(row) => row.name} empty="Aucun scénario enregistré — enregistrez d'abord une hypothèse." />
      </section>

      <section style={sectionStyle}>
        <h2 style={h2Style}>Tabs — navigation clavier (←/→, Home/End)</h2>
        <Tabs items={TAB_ITEMS} value={tab} onChange={setTab} ariaLabel="Vitrine" />
        <p style={{ margin: 0, color: "var(--muted)", fontSize: "var(--fs-13)" }}>Onglet actif : {tab}</p>
      </section>

      <section style={sectionStyle}>
        <h2 style={h2Style}>Progress — determinate / indeterminate / reduced-motion</h2>
        <ProgressBar label="Simulation en cours" value={0.62} />
        <ProgressBar label="Analyse de sensibilité" />
      </section>

      <section style={sectionStyle}>
        <h2 style={h2Style}>EmptyState — titre + description + action</h2>
        <EmptyState
          title="Aucun résultat à afficher"
          description="Lancez une simulation pour obtenir les graphiques et la narration."
          action={<Button size="small">Lancer la simulation</Button>}
        />
      </section>

      <section style={sectionStyle}>
        <h2 style={h2Style}>Dataviz — planche des 10 séries (Viénot : ΔE min 13.6, contraste ≥ 3.2:1)</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "var(--sp-2)" }}>
          {SERIES.map((serie, index) => (
            <div
              key={serie.name}
              style={{
                display: "grid",
                justifyItems: "start",
                gap: "var(--sp-1)",
                padding: "var(--sp-2) var(--sp-3)",
                border: "1px solid var(--border)",
                borderRadius: "var(--r-2)",
                background: "var(--bg-inset)",
              }}
            >
              <span
                style={{ display: "inline-block", width: 24, height: 6, borderRadius: 3, background: `var(--series-${index + 1})` }}
                aria-hidden="true"
              />
              <span style={{ color: "var(--text)", fontSize: "var(--fs-12)", fontFamily: "var(--font-data)" }}>
                S{index + 1}
              </span>
              <span style={{ color: "var(--muted)", fontSize: "var(--fs-11)" }}>{serie.name}</span>
            </div>
          ))}
        </div>
        <p style={{ margin: 0, color: "var(--faint)", fontSize: "var(--fs-12)" }}>
          Attribution STABLE : le scénario 1 est toujours S1, quel que soit l'écran. L'accent cyan reste réservé à l'interactif.
        </p>
      </section>

      <section style={sectionStyle}>
        <h2 style={h2Style}>LineChart — 3 scénarios comparés, légende interactive</h2>
        <LineChart
          title="Profit cumulé par scénario"
          description="Chaque scénario garde sa couleur entre les écrans et les re-rendus."
          series={scenarioLines}
          formatY={(value) => fmtFcfa(value)}
          formatX={(index) => `M${index}`}
          legend
          ariaLabel="Comparaison du profit cumulé de trois scénarios sur douze mois"
        />
      </section>

      <section style={sectionStyle}>
        <h2 style={h2Style}>Histogram — distribution + percentiles (P50 = référence)</h2>
        <Histogram
          title="Distribution du profit"
          description="8 000 simulations — bande P10/P50/P90."
          bins={demoBins}
          percentiles={demoPercentiles}
          formatX={(value) => fmtFcfa(value)}
        />
      </section>

      <section style={sectionStyle}>
        <h2 style={h2Style}>DivergingBars — tornade de sensibilité</h2>
        <DivergingBars
          title="Contribution à la variance du profit"
          description="Positif : la hausse de l'hypothèse augmente le profit."
          rows={demoTornado}
          formatValue={(value) => fmtFcfa(value)}
        />
      </section>

      <section style={sectionStyle}>
        <h2 style={h2Style}>Sparkline — micro-ligne inline + Stat avec unité</h2>
        <div style={{ display: "flex", gap: "var(--sp-4)", flexWrap: "wrap", alignItems: "center" }}>
          <Stat label="Demande (6 derniers mois)" value="410" unit="unités" hint="Tendance en hausse" />
          <Sparkline values={sparkValues} seriesIndex={0} ariaLabel="Tendance de la demande sur six mois" />
          <Sparkline values={[30, 44, 41, 62, 55, 70]} seriesIndex={1} ariaLabel="Tendance du panier moyen" />
        </div>
      </section>
    </div>
  );
}
