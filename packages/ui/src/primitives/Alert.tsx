import type { ReactNode } from "react";
import { cx } from "../cx";
import { Button } from "./Button";

export type AlertTone = "neutral" | "ok" | "warn" | "danger";

export type AlertAction = {
  label: string;
  onClick: () => void;
};

/**
 * Message inline. PRINCIPE SNYK (charte, refont/03) : un message qui ne
 * dit pas quoi faire vaut moins que la moitié d'un message — `title` est
 * donc obligatoire (quoi), `children` porte le pourquoi (humain), et
 * `action` propose la suite (quoi faire maintenant).
 *
 * A11y : `role="status"` pour les annonces non bloquantes.
 */
export function InlineAlert({
  tone = "neutral",
  title,
  action,
  children,
}: {
  tone?: AlertTone;
  title: string;
  action?: AlertAction;
  children: ReactNode;
}) {
  return (
    <div className={cx("ui-alert", `ui-alert--${tone}`)} role="status">
      <div className="ui-alert__row">
        <strong>{title}</strong>
        {action ? (
          <Button variant="ghost" size="small" onClick={action.onClick}>
            {action.label}
          </Button>
        ) : null}
      </div>
      <div>{children}</div>
    </div>
  );
}
