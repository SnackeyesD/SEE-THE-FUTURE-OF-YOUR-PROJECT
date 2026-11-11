import { serieStyle } from "./scale";

export type LegendItem = {
  id: string;
  label: string;
  seriesIndex: number;
};

/**
 * Légende interactive : chaque item est un bouton `aria-pressed` —
 * cliquer masque/montre la série (état possédé par le chart hôte).
 * A11y : la couleur du chip ne porte jamais seule l'information,
 * le libellé texte est toujours présent.
 */
export function Legend({
  items,
  hidden,
  onToggle,
}: {
  items: LegendItem[];
  hidden: ReadonlySet<string>;
  onToggle: (id: string) => void;
}) {
  return (
    <div className="viz__legend" role="group" aria-label="Séries du graphique">
      {items.map((item) => {
        const off = hidden.has(item.id);
        return (
          <button
            key={item.id}
            type="button"
            aria-pressed={!off}
            onClick={() => onToggle(item.id)}
          >
            <span className="viz__legend__chip" style={serieStyle(item.seriesIndex)} aria-hidden="true" />
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
