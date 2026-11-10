import {
  createContext,
  useContext,
  useId,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from "react";
import { cx } from "./cx";

const DensityContext = createContext<"comfortable" | "compact">("comfortable");

export function DensityProvider({
  value,
  children,
}: {
  value: "comfortable" | "compact";
  children: ReactNode;
}) {
  return <DensityContext.Provider value={value}>{children}</DensityContext.Provider>;
}

export function useDensity() {
  return useContext(DensityContext);
}

export function Card({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLElement> & { children: ReactNode }) {
  return (
    <article className={cx("ui-card", className)} {...props}>
      {children}
    </article>
  );
}

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

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

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

export function Badge({
  tone = "neutral",
  children,
}: {
  tone?: "neutral" | "ok" | "warn" | "danger" | "accent";
  children: ReactNode;
}) {
  return <span className={cx("ui-badge", `ui-badge--${tone}`)}>{children}</span>;
}

export function Field({
  label,
  hint,
  error,
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  error?: string;
}) {
  const id = useId();
  return (
    <label className={cx("ui-field", className)} htmlFor={id}>
      <span>{label}</span>
      <input id={id} {...props} aria-invalid={Boolean(error)} />
      {error ? <span className="ui-field__error">{error}</span> : null}
      {!error && hint ? <span className="ui-field__hint">{hint}</span> : null}
    </label>
  );
}

export function SelectField({
  label,
  hint,
  className,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <label className={cx("ui-field", className)} htmlFor={id}>
      <span>{label}</span>
      <select id={id} {...props}>
        {children}
      </select>
      {hint ? <span className="ui-field__hint">{hint}</span> : null}
    </label>
  );
}

export function TextareaField({
  label,
  hint,
  value,
  onChange,
  rows = 4,
  placeholder,
  className,
}: {
  label: string;
  hint?: string;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  placeholder?: string;
  className?: string;
}) {
  const id = useId();
  return (
    <label className={cx("ui-field", className)} htmlFor={id}>
      <span>{label}</span>
      <textarea
        id={id}
        value={value}
        rows={rows}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
      {hint ? <span className="ui-field__hint">{hint}</span> : null}
    </label>
  );
}

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

export function ProgressBar({
  value,
  label,
}: {
  value?: number;
  label: string;
}) {
  const clamped =
    value === undefined ? undefined : Math.max(0, Math.min(1, value));
  return (
    <div className="ui-progress">
      <div className="ui-progress__head">
        <span>{label}</span>
        <span>{clamped === undefined ? "…" : `${Math.round(clamped * 100)} %`}</span>
      </div>
      <div
        className={cx("ui-progress__track", clamped === undefined && "ui-progress__track--indeterminate")}
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={clamped === undefined ? undefined : Math.round(clamped * 100)}
      >
        <span style={clamped === undefined ? undefined : { width: `${clamped * 100}%` }} />
      </div>
    </div>
  );
}

export function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "ok" | "danger" | "neutral";
}) {
  return (
    <div className={cx("ui-stat", tone && `ui-stat--${tone}`)}>
      <span className="ui-stat__label">{label}</span>
      <strong className="ui-stat__value">{value}</strong>
      {hint ? <span className="ui-stat__hint">{hint}</span> : null}
    </div>
  );
}

export function InlineAlert({
  tone = "neutral",
  title,
  children,
}: {
  tone?: "neutral" | "ok" | "warn" | "danger";
  title?: string;
  children: ReactNode;
}) {
  return (
    <div className={cx("ui-alert", `ui-alert--${tone}`)} role="status">
      {title ? <strong>{title}</strong> : null}
      <div>{children}</div>
    </div>
  );
}
