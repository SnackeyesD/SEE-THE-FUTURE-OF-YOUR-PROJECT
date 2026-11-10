import type { ReactNode } from "react";
import { cx } from "../cx";

export type TableColumn<Row> = {
  /** Clé de la colonne ; sert de défaut pour `render`. */
  key: string;
  /** En-tête (rendu en mono uppercase par le CSS). */
  header: string;
  /** Valeurs numériques/comparées : mono tabulaire, alignées à droite (charte R4). */
  mono?: boolean;
  /** Largeur CSS de la colonne (ex. "120px"). */
  width?: string;
  /** Rendu personnalisé de la cellule (badge, lien…). */
  render?: (row: Row) => ReactNode;
};

/**
 * Table de données « Ink & Signal » :
 * en-têtes en mono uppercase, chiffres tabulaires alignés à droite,
 * zébrage discret (`--bg-veil-soft`), état vide explicite.
 *
 * Sans dépendance métier — les lignes sont typées par l'appelant.
 */
export function Table<Row>({
  columns,
  rows,
  rowKey,
  empty = "Aucune donnée.",
  className,
}: {
  columns: Array<TableColumn<Row>>;
  rows: Row[];
  rowKey: (row: Row, index: number) => string | number;
  empty?: string;
  className?: string;
}) {
  if (rows.length === 0) {
    return <p className={cx("ui-muted", className)}>{empty}</p>;
  }
  return (
    <div className={className} style={{ overflowX: "auto" }}>
      <table className="ui-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                style={column.width ? { width: column.width } : undefined}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={rowKey(row, index)}>
              {columns.map((column) => {
                const content = column.render
                  ? column.render(row)
                  : ((row as Record<string, unknown>)[column.key] as ReactNode);
                return (
                  <td
                    key={column.key}
                    className={cx(column.mono && "td--num")}
                    style={column.mono ? { textAlign: "right" } : undefined}
                  >
                    {content}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
