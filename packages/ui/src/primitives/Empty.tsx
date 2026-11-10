import type { ReactNode } from "react";

/**
 * État vide. Doit dire : où on est (title), quoi faire (description),
 * et proposer l'action (CTA). Un état vide sans action est un bug
 * de design (charte R-principe Snyk).
 */
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="ui-empty">
      <strong>{title}</strong>
      <p>{description}</p>
      {action}
    </div>
  );
}
