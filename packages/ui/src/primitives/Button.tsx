import type { ButtonHTMLAttributes } from "react";
import { cx } from "../cx";
import { useDensity } from "./density";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

/**
 * Bouton de la librairie « Ink & Signal ».
 *
 * Variants : primary (accent — interactif), secondary (surface élevée),
 * ghost (bordure seule), danger (état destructif).
 * Focus visible par défaut (`.ui-button:focus-visible`).
 */
export function Button({
  variant = "primary",
  size = "medium",
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "small" | "medium";
}) {
  const density = useDensity();
  return (
    <button
      type={props.type ?? "button"}
      className={cx(
        "ui-button",
        `ui-button--${variant}`,
        size === "small" && "ui-button--small",
        density === "compact" && "ui-button--compact",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
