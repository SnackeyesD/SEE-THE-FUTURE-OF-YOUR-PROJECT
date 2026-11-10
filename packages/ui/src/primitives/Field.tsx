import {
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from "react";
import { cx } from "../cx";

/**
 * Champ texte avec label, hint et erreur. L'erreur est un message
 * actionnable (principe Snyk) : dire quoi corriger, pas juste « invalide ».
 * A11y : label relié par `for`/`id` générés, `aria-invalid` sur erreur.
 */
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

/**
 * Champ liste déroulante. Mêmes règles de label/hint que `Field`.
 */
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

/**
 * Champ multiligne contrôlé.
 */
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
