import type { SensitivityEntry } from "@see/protocol";
import { DivergingBars } from "@see/ui";

import { ASSUMPTION_BY_KEY } from "../../lib/assumptions";
import { formatCurrency } from "../../lib/format";

export interface TornadoProps {
  entries: SensitivityEntry[];
  currency: string;
  /** Clé d'hypothèse actuellement ciblée (synchronisée avec le panneau). */
  selected?: string | null;
  /** Sélection d'une barre : cible l'hypothèse correspondante. */
  onSelect?: (key: string) => void;
}

/**
 * Tornade de sensibilité interactive : la barre la plus contributive est
 * cliquable (ou activable au clavier) et cible l'hypothèse dans le panneau.
 * Les contributions viennent du moteur ; aucun recalcul ici.
 */
export function Tornado({ entries, currency, selected, onSelect }: TornadoProps) {
  if (entries.length === 0) {
    return <p className="ui-muted">Aucune sensibilité disponible pour ce run.</p>;
  }

  const top = [...entries]
    .sort((left, right) => Math.abs(right.contribution) - Math.abs(left.contribution))
    .slice(0, 8);

  const keyByLabel = new Map<string, string>();
  const rows = top.map((entry) => {
    const spec = ASSUMPTION_BY_KEY.get(entry.hypothesis);
    const label = spec?.label ?? entry.hypothesis;
    keyByLabel.set(label, entry.hypothesis);
    return {
      label,
      value: entry.contribution,
      tooltip: `Corrélation ${entry.correlation.toFixed(2)} · ${formatCurrency(
        entry.contribution,
        currency,
        { compact: true },
      )}`,
    };
  });

  const selectedLabel = selected
    ? (ASSUMPTION_BY_KEY.get(selected)?.label ?? selected)
    : undefined;

  return (
    <DivergingBars
      title="Analyse de sensibilité"
      description="Contribution de chaque hypothèse à la variance du profit — corrélation, pas causalité. Cliquez une barre pour cibler l'hypothèse."
      rows={rows}
      formatValue={(value) => formatCurrency(value, currency, { compact: true })}
      ariaLabel="Diagramme tornade interactif de la sensibilité du profit"
      selectedLabel={selectedLabel}
      onSelectRow={
        onSelect
          ? (row) => {
              const key = keyByLabel.get(row.label);
              if (key) onSelect(key);
            }
          : undefined
      }
    />
  );
}
