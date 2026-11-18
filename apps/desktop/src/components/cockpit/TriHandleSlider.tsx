import {
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from "react";

export interface TriValue {
  low: number;
  mode: number;
  high: number;
}

export type TriHandle = keyof TriValue;

const HANDLE_ORDER: TriHandle[] = ["low", "mode", "high"];
const HANDLE_LABELS: Record<TriHandle, string> = {
  low: "minimum",
  mode: "mode",
  high: "maximum",
};

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(Math.max(value, min), max);
}

/**
 * Curseur à trois poignées min / mode / max.
 *
 * - la contrainte `min ≤ mode ≤ max` est appliquée **pendant** le geste ;
 * - chaque poignée est un `slider` clavier (flèches, Page↑/↓, Home/End) ;
 * - double-clic : saisie numérique du handle ;
 * - aucun calcul métier : `onChange` remonte la valeur, le parent décide de la
 *   distribution et de la commande coalescée.
 */
export function TriHandleSlider({
  label,
  unit,
  value,
  domain,
  step,
  disabled = false,
  formatValue = (number) => String(number),
  onChange,
}: {
  label: string;
  unit?: string;
  value: TriValue;
  domain: [number, number];
  step?: number;
  disabled?: boolean;
  formatValue?: (value: number) => string;
  onChange: (next: TriValue, commit: boolean) => void;
}) {
  const trackRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{
    key: TriHandle;
    startX: number;
    start: TriValue;
    width: number;
  } | null>(null);
  const [editing, setEditing] = useState<TriHandle | null>(null);
  const [draft, setDraft] = useState("");

  const span = Math.max(1e-9, domain[1] - domain[0]);
  const stepValue = step ?? span / 100;

  const percent = (number: number): number =>
    clamp(((number - domain[0]) / span) * 100, 0, 100);

  const trianglePath = `M ${percent(value.low)} 26 L ${percent(value.mode)} 2 L ${percent(
    value.high,
  )} 26`;

  const bound = (key: TriHandle, candidate: number, base: TriValue): number => {
    const rounded =
      step !== undefined && step > 0
        ? Math.round(candidate / step) * step
        : candidate;
    if (key === "low") return clamp(rounded, domain[0], base.mode);
    if (key === "high") return clamp(rounded, base.mode, domain[1]);
    return clamp(rounded, base.low, base.high);
  };

  const nextValue = (key: TriHandle, candidate: number, base: TriValue): TriValue => {
    const bounded = bound(key, candidate, base);
    return { ...base, [key]: bounded };
  };

  const beginDrag =
    (key: TriHandle) => (event: PointerEvent<HTMLDivElement>) => {
      if (disabled) return;
      const width = trackRef.current?.getBoundingClientRect().width ?? 0;
      if (width <= 0) return;
      event.preventDefault();
      const start = value;
      let latest = value;
      dragRef.current = { key, startX: event.clientX, start, width };

      const move = (moveEvent: globalThis.PointerEvent): void => {
        const drag = dragRef.current;
        if (!drag) return;
        const delta = ((moveEvent.clientX - drag.startX) / drag.width) * span;
        latest = nextValue(drag.key, drag.start[drag.key] + delta, drag.start);
        onChange(latest, false);
      };
      const stop = (): void => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", stop);
        window.removeEventListener("pointercancel", stop);
        dragRef.current = null;
        onChange(latest, true);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", stop);
      window.addEventListener("pointercancel", stop);
    };

  const handleKey = (key: TriHandle) => (event: KeyboardEvent<HTMLDivElement>) => {
    if (disabled) return;
    const current = value[key];
    const commit = (candidate: number): void => {
      onChange(nextValue(key, candidate, value), true);
    };
    switch (event.key) {
      case "ArrowRight":
      case "ArrowUp":
        event.preventDefault();
        commit(current + stepValue);
        break;
      case "ArrowLeft":
      case "ArrowDown":
        event.preventDefault();
        commit(current - stepValue);
        break;
      case "PageUp":
        event.preventDefault();
        commit(current + stepValue * 10);
        break;
      case "PageDown":
        event.preventDefault();
        commit(current - stepValue * 10);
        break;
      case "Home":
        event.preventDefault();
        commit(key === "low" ? domain[0] : key === "mode" ? value.low : value.mode);
        break;
      case "End":
        event.preventDefault();
        commit(key === "high" ? domain[1] : key === "mode" ? value.high : value.mode);
        break;
      default:
        break;
    }
  };

  const openEditor = (key: TriHandle): void => {
    if (disabled) return;
    setEditing(key);
    setDraft(String(value[key]));
  };

  const commitEditor = (): void => {
    if (!editing) return;
    const parsed = Number(draft.replace(",", "."));
    if (Number.isFinite(parsed)) {
      onChange(nextValue(editing, parsed, value), true);
    }
    setEditing(null);
  };

  const editorKey = (event: KeyboardEvent<HTMLInputElement>): void => {
    if (event.key === "Enter") {
      event.preventDefault();
      commitEditor();
    } else if (event.key === "Escape") {
      event.preventDefault();
      setEditing(null);
    }
  };

  return (
    <div className="tri-slider" data-disabled={disabled || undefined}>
      <div className="tri-slider__head">
        <span className="tri-slider__label">{label}</span>
        <span className="tri-slider__value">
          {formatValue(value.mode)}
          {unit ? <span className="tri-slider__unit">{unit}</span> : null}
        </span>
      </div>

      <svg
        className="tri-slider__preview"
        viewBox="0 0 100 28"
        preserveAspectRatio="none"
        aria-hidden="true"
        focusable="false"
      >
        <line className="tri-slider__baseline" x1="0" x2="100" y1="26" y2="26" />
        <path className="tri-slider__shape" d={trianglePath} />
      </svg>

      <div className="tri-slider__track" ref={trackRef}>
        <span
          className="tri-slider__range"
          style={{
            left: `${percent(value.low)}%`,
            width: `${Math.max(0, percent(value.high) - percent(value.low))}%`,
          }}
        />
        {HANDLE_ORDER.map((key) => (
          <div
            key={key}
            className={
              key === "mode"
                ? "tri-slider__handle tri-slider__handle--mode"
                : "tri-slider__handle"
            }
            style={{ left: `${percent(value[key])}%` }}
            role="slider"
            tabIndex={disabled ? -1 : 0}
            aria-label={`${label} — ${HANDLE_LABELS[key]}`}
            aria-orientation="horizontal"
            aria-valuemin={
              key === "low" ? domain[0] : key === "mode" ? value.low : value.mode
            }
            aria-valuemax={
              key === "high" ? domain[1] : key === "mode" ? value.high : value.mode
            }
            aria-valuenow={value[key]}
            aria-valuetext={`${formatValue(value[key])}${unit ? ` ${unit}` : ""}`}
            aria-disabled={disabled || undefined}
            onPointerDown={beginDrag(key)}
            onKeyDown={handleKey(key)}
            onDoubleClick={() => openEditor(key)}
          >
            <span className="tri-slider__grip" aria-hidden="true" />
          </div>
        ))}
      </div>

      <div className="tri-slider__range-text">
        {`min ${formatValue(value.low)} · mode ${formatValue(value.mode)} · max ${formatValue(
          value.high,
        )}`}
      </div>

      {editing ? (
        <input
          className="tri-slider__editor"
          aria-label={`${label} — ${HANDLE_LABELS[editing]} (saisie)`}
          inputMode="decimal"
          value={draft}
          autoFocus
          onChange={(event) => setDraft(event.target.value)}
          onBlur={commitEditor}
          onKeyDown={editorKey}
        />
      ) : null}
    </div>
  );
}
