import type { ReactNode } from "react";
import { cx } from "../cx";

export type BadgeTone = "neutral" | "ok" | "warn" | "danger" | "accent";

/**
 * Badge d'état. Le ton porte le sens ; le texte reste obligatoire
 * (la couleur ne porte jamais seule l'information — WCAG 1.4.1).
 */
export function Badge({
  tone = "neutral",
  children,
}: {
  tone?: BadgeTone;
  children: ReactNode;
}) {
  return <span className={cx("ui-badge", `ui-badge--${tone}`)}>{children}</span>;
}
