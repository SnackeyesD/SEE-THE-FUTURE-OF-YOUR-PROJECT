import type { HTMLAttributes, ReactNode } from "react";

/**
 * Carte — surface standard du système. Contenu libre ; en-tête via
 * `CardHeader`. Les cartes n'ajoutent jamais de couleur de décoration
 * (fond = `--bg-surface`, bordure = `--border`).
 */
export function Card({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLElement> & { children: ReactNode }) {
  return (
    <article className={`ui-card${className ? ` ${className}` : ""}`} {...props}>
      {children}
    </article>
  );
}

/**
 * En-tête de carte : eyebrow (accent, uppercase), titre, description
 * et zone d'action à droite.
 */
export function CardHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <header className="ui-card__header">
      <div>
        {eyebrow ? <p className="ui-eyebrow">{eyebrow}</p> : null}
        <h2>{title}</h2>
        {description ? <p className="ui-muted">{description}</p> : null}
      </div>
      {action ? <div className="ui-card__action">{action}</div> : null}
    </header>
  );
}
