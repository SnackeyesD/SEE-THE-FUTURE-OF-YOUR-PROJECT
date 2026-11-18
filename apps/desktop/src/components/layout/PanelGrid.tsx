import { useCallback, useRef, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";

import {
  MIN_FRACTION,
  PRESET_LABELS,
  PRESET_NAMES,
  clampFraction,
  customLayout,
  layoutFromPreset,
  type LayoutState,
  type PresetName,
} from "../../store/layout";

export interface PanelGridProps {
  layout: LayoutState;
  onLayoutChange: (layout: LayoutState) => void;
  left: ReactNode;
  main: ReactNode;
  right: ReactNode;
  header?: ReactNode;
  footer?: ReactNode;
}

type HandleSide = "left" | "right";

const HANDLE_STEP = 0.02;
const HANDLE_STEP_FAST = 0.05;

export function PanelGrid({
  layout,
  onLayoutChange,
  left,
  main,
  right,
  header,
  footer,
}: PanelGridProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  const resize = useCallback(
    (side: HandleSide, delta: number) => {
      const { fractions, fullscreen } = layout;
      if (side === "left") {
        const nextLeft = clampFraction(fractions.left + delta, fractions.right);
        const nextMain = 1 - nextLeft - fractions.right;
        if (nextMain < MIN_FRACTION) return;
        onLayoutChange(
          customLayout({ left: nextLeft, main: nextMain, right: fractions.right }, fullscreen),
        );
        return;
      }
      const nextRight = clampFraction(fractions.right - delta, fractions.left);
      const nextMain = 1 - fractions.left - nextRight;
      if (nextMain < MIN_FRACTION) return;
      onLayoutChange(
        customLayout({ left: fractions.left, main: nextMain, right: nextRight }, fullscreen),
      );
    },
    [layout, onLayoutChange],
  );

  const startDrag = useCallback(
    (side: HandleSide) => (event: PointerEvent<HTMLDivElement>) => {
      const width = containerRef.current?.getBoundingClientRect().width ?? 0;
      if (width <= 0) return;
      event.preventDefault();
      const startX = event.clientX;
      const start = layout.fractions;

      const apply = (clientX: number): void => {
        const delta = (clientX - startX) / width;
        if (side === "left") {
          const nextLeft = clampFraction(start.left + delta, start.right);
          const nextMain = 1 - nextLeft - start.right;
          if (nextMain < MIN_FRACTION) return;
          onLayoutChange(
            customLayout(
              { left: nextLeft, main: nextMain, right: start.right },
              layout.fullscreen,
            ),
          );
          return;
        }
        const nextRight = clampFraction(start.right - delta, start.left);
        const nextMain = 1 - start.left - nextRight;
        if (nextMain < MIN_FRACTION) return;
        onLayoutChange(
          customLayout(
            { left: start.left, main: nextMain, right: nextRight },
            layout.fullscreen,
          ),
        );
      };

      const move = (moveEvent: globalThis.PointerEvent): void => apply(moveEvent.clientX);
      const stop = (): void => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", stop);
        window.removeEventListener("pointercancel", stop);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", stop);
      window.addEventListener("pointercancel", stop);
    },
    [layout, onLayoutChange],
  );

  const resizeWithKeyboard = useCallback(
    (side: HandleSide) => (event: KeyboardEvent<HTMLDivElement>) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const step = event.shiftKey ? HANDLE_STEP_FAST : HANDLE_STEP;
      resize(side, event.key === "ArrowLeft" ? -step : step);
    },
    [resize],
  );

  const preset = (name: PresetName): void => {
    onLayoutChange(layoutFromPreset(name));
  };

  const fullscreen = (target: "main" | "secondary" | null): void => {
    onLayoutChange({ ...layout, fullscreen: target });
  };

  const fractions = layout.fractions;

  return (
    <div className="panel-grid" data-preset={layout.preset}>
      <div className="panel-grid__toolbar" role="toolbar" aria-label="Disposition">
        {PRESET_NAMES.map((name) => (
          <button
            key={name}
            type="button"
            className="panel-grid__preset"
            aria-pressed={layout.preset === name}
            onClick={() => preset(name)}
          >
            Disposition {PRESET_LABELS[name]}
          </button>
        ))}
        <button
          type="button"
          className="panel-grid__preset"
          aria-pressed={layout.fullscreen === "main"}
          onClick={() => fullscreen(layout.fullscreen === "main" ? null : "main")}
        >
          Plein écran principal
        </button>
        <button
          type="button"
          className="panel-grid__preset"
          aria-pressed={layout.fullscreen === "secondary"}
          onClick={() => fullscreen(layout.fullscreen === "secondary" ? null : "secondary")}
        >
          Plein écran secondaire
        </button>
      </div>

      {header ? <div className="panel-grid__header">{header}</div> : null}

      {layout.fullscreen ? (
        <div className="panel-grid__fullscreen" data-panel={layout.fullscreen}>
          <button
            type="button"
            className="panel-grid__exit"
            onClick={() => fullscreen(null)}
          >
            Quitter le plein écran
          </button>
          {layout.fullscreen === "main" ? (
            <section className="panel-grid__panel" aria-label="Principal">
              {main}
            </section>
          ) : (
            <section className="panel-grid__panel" aria-label="Secondaire">
              {right}
            </section>
          )}
        </div>
      ) : (
        <div
          ref={containerRef}
          className="panel-grid__grid"
          style={{
            gridTemplateColumns: `${fractions.left}fr 10px ${fractions.main}fr 10px ${fractions.right}fr`,
          }}
        >
          <section className="panel-grid__panel" aria-label="Hypothèses">
            {left}
          </section>
          <div
            className="panel-grid__handle"
            role="separator"
            aria-orientation="vertical"
            aria-label="Redimensionner les hypothèses"
            tabIndex={0}
            onPointerDown={startDrag("left")}
            onKeyDown={resizeWithKeyboard("left")}
          />
          <section className="panel-grid__panel" aria-label="Principal">
            {main}
          </section>
          <div
            className="panel-grid__handle"
            role="separator"
            aria-orientation="vertical"
            aria-label="Redimensionner le panneau secondaire"
            tabIndex={0}
            onPointerDown={startDrag("right")}
            onKeyDown={resizeWithKeyboard("right")}
          />
          <section className="panel-grid__panel" aria-label="Secondaire">
            {right}
          </section>
        </div>
      )}

      {footer ? <div className="panel-grid__footer">{footer}</div> : null}
    </div>
  );
}
