import type { ScenarioEvent } from "@see/protocol";
import { EVENT_CATALOG_BY_TYPE } from "@see/protocol";
import { Badge, Button } from "@see/ui";
import {
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from "react";

import {
  clampWindow,
  laneAssignment,
  lastMonth,
  moveWindow,
  resizeEnd,
  resizeStart,
  windowToPercent,
  xToMonth,
  type EventWindow,
} from "./events";

const LANE_HEIGHT = 34;
const TRACK_PADDING = 8;

type DragMode = "move" | "start" | "end";

interface DragState {
  id: string;
  mode: DragMode;
  startX: number;
  origin: EventWindow;
  width: number;
  preview: EventWindow;
}

function catalogLabel(event: ScenarioEvent): string {
  return EVENT_CATALOG_BY_TYPE[event.type]?.label ?? event.type;
}

function describe(event: ScenarioEvent, window: EventWindow): string {
  const enabled = event.enabled === false ? "désactivé" : "actif";
  const probability =
    event.probability === undefined ? "100 %" : `${Math.round(event.probability * 100)} %`;
  return `${catalogLabel(event)} — mois ${window.startMonth} à ${lastMonth(window)}, ${window.durationMonths} mois, probabilité ${probability}, ${enabled}`;
}

/**
 * Frise d'événements.
 *
 * Le glissement met à jour un aperçu **local** (aucune simulation) ; un seul
 * `onChange(..., true)` est émis au relâchement. Le clavier offre les mêmes
 * opérations sans glisser-déposer : flèches pour déplacer, `Shift` pour la
 * durée, `Alt` pour le début, `Entrée` pour éditer, `Suppr` pour supprimer et
 * `Espace` pour activer/désactiver.
 */
export function EventTimeline({
  events,
  horizon,
  selectedId,
  disabled = false,
  onSelect,
  onChange,
  onToggle,
  onDuplicate,
  onDelete,
  onEdit,
  onOpenCatalog,
  onSelectMonth,
}: {
  events: readonly ScenarioEvent[];
  horizon: number;
  selectedId: string | null;
  disabled?: boolean;
  onSelect: (id: string | null) => void;
  onChange: (id: string, window: EventWindow, commit: boolean) => void;
  onToggle: (id: string) => void;
  onDuplicate: (id: string) => void;
  onDelete: (id: string) => void;
  onEdit: (id: string) => void;
  onOpenCatalog: () => void;
  onSelectMonth: (month: number) => void;
}) {
  const trackRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const [preview, setPreview] = useState<{ id: string; window: EventWindow } | null>(null);
  const [menuId, setMenuId] = useState<string | null>(null);

  const { lanes, count } = useMemo(() => laneAssignment(events), [events]);
  const height = Math.max(1, count) * LANE_HEIGHT + TRACK_PADDING * 2;

  const trackWidth = (): number => trackRef.current?.clientWidth ?? 0;

  const pointerDown = (
    event: PointerEvent<HTMLElement>,
    target: ScenarioEvent,
    mode: DragMode,
  ): void => {
    if (disabled) return;
    event.preventDefault();
    event.stopPropagation();
    onSelect(target.id);
    event.currentTarget.setPointerCapture?.(event.pointerId);
    dragRef.current = {
      id: target.id,
      mode,
      startX: event.clientX,
      origin: {
        startMonth: target.startMonth,
        durationMonths: target.durationMonths,
      },
      width: Math.max(1, trackWidth()),
      preview: {
        startMonth: target.startMonth,
        durationMonths: target.durationMonths,
      },
    };
    setPreview({ id: target.id, window: { startMonth: target.startMonth, durationMonths: target.durationMonths } });
  };

  const pointerMove = (event: PointerEvent<HTMLElement>): void => {
    const drag = dragRef.current;
    if (!drag) return;
    const deltaMonths = Math.round(
      ((event.clientX - drag.startX) / drag.width) * Math.max(1, horizon),
    );
    const next =
      drag.mode === "move"
        ? moveWindow(drag.origin, deltaMonths, horizon)
        : drag.mode === "start"
          ? resizeStart(drag.origin, deltaMonths, horizon)
          : resizeEnd(drag.origin, deltaMonths, horizon);
    if (
      next.startMonth === drag.preview.startMonth &&
      next.durationMonths === drag.preview.durationMonths
    ) {
      return;
    }
    drag.preview = next;
    setPreview({ id: drag.id, window: next });
  };

  const pointerUp = (): void => {
    const drag = dragRef.current;
    dragRef.current = null;
    setPreview(null);
    if (!drag) return;
    const changed =
      drag.preview.startMonth !== drag.origin.startMonth ||
      drag.preview.durationMonths !== drag.origin.durationMonths;
    if (changed) {
      onChange(drag.id, clampWindow(drag.preview, horizon), true);
    }
  };

  /** Annulation système (tactile, perte de capture) : aucun calcul. */
  const cancelDrag = (): void => {
    dragRef.current = null;
    setPreview(null);
  };

  const keyDown = (event: KeyboardEvent<HTMLElement>, target: ScenarioEvent): void => {
    if (disabled) return;
    const window: EventWindow = {
      startMonth: target.startMonth,
      durationMonths: target.durationMonths,
    };
    const delta = event.key === "ArrowLeft" ? -1 : event.key === "ArrowRight" ? 1 : 0;

    if (delta !== 0) {
      event.preventDefault();
      event.stopPropagation();
      const next = event.shiftKey
        ? resizeEnd(window, delta, horizon)
        : event.altKey
          ? resizeStart(window, delta, horizon)
          : moveWindow(window, delta, horizon);
      if (
        next.startMonth !== window.startMonth ||
        next.durationMonths !== window.durationMonths
      ) {
        onChange(target.id, next, true);
      }
      return;
    }
    if (event.key === "Delete" || event.key === "Backspace") {
      event.preventDefault();
      onDelete(target.id);
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      onEdit(target.id);
      return;
    }
    if (event.key === " ") {
      event.preventDefault();
      onToggle(target.id);
      return;
    }
    if (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10")) {
      event.preventDefault();
      setMenuId(target.id);
    }
  };

  const trackClick = (event: PointerEvent<HTMLDivElement>): void => {
    if ((event.target as HTMLElement).closest("[data-event-block]")) return;
    const rect = event.currentTarget.getBoundingClientRect();
    onSelectMonth(xToMonth(event.clientX - rect.left, horizon, rect.width));
    onSelect(null);
    setMenuId(null);
  };

  return (
    <section className="cockpit-timeline" aria-label="Frise d'événements">
      <div className="cockpit-timeline__head">
        <div>
          <strong>Événements</strong>
          <span className="ui-muted">
            {events.length === 0
              ? " · aucun imprévu daté"
              : ` · ${events.length} sur ${horizon} mois`}
          </span>
        </div>
        <Button variant="secondary" size="small" onClick={onOpenCatalog} disabled={disabled}>
          Ajouter un événement
        </Button>
      </div>

      <div
        ref={trackRef}
        className="cockpit-timeline__track"
        style={{ height }}
        role="group"
        aria-label="Chronologie des événements"
        data-hotkeys-timeline="true"
        onPointerDown={trackClick}
      >
        {events.length === 0 ? (
          <p className="cockpit-timeline__empty ui-muted">
            Aucun événement : ajoutez un imprévu depuis le catalogue, il sera placé au mois
            sélectionné.
          </p>
        ) : null}

        {events.map((event) => {
          const active = preview?.id === event.id ? preview.window : null;
          const window: EventWindow = active ?? {
            startMonth: event.startMonth,
            durationMonths: event.durationMonths,
          };
          const geometry = windowToPercent(window, horizon);
          const lane = lanes.get(event.id) ?? 0;
          const selected = selectedId === event.id;
          const disabledEvent = event.enabled === false;
          return (
            <div
              key={event.id}
              data-event-block="true"
              data-event-type={event.type}
              className={[
                "cockpit-event",
                selected && "cockpit-event--selected",
                disabledEvent && "cockpit-event--disabled",
                preview?.id === event.id && "cockpit-event--dragging",
              ]
                .filter(Boolean)
                .join(" ")}
              style={{
                left: `${geometry.left}%`,
                width: `${geometry.width}%`,
                top: `${TRACK_PADDING + lane * LANE_HEIGHT}px`,
              }}
            >
              <button
                type="button"
                className="cockpit-event__body"
                aria-label={describe(event, window)}
                aria-pressed={selected}
                disabled={disabled}
                onPointerDown={(pointerEvent) => pointerDown(pointerEvent, event, "move")}
                onPointerMove={pointerMove}
                onPointerUp={pointerUp}
                onPointerCancel={cancelDrag}
                onKeyDown={(keyEvent) => keyDown(keyEvent, event)}
                onDoubleClick={() => onEdit(event.id)}
                onContextMenu={(contextEvent) => {
                  contextEvent.preventDefault();
                  onSelect(event.id);
                  setMenuId(event.id);
                }}
              >
                <span className="cockpit-event__label">{catalogLabel(event)}</span>
                <span className="cockpit-event__meta">
                  {window.startMonth}–{lastMonth(window)} · {window.durationMonths} mois
                </span>
              </button>

              <span
                className="cockpit-event__handle cockpit-event__handle--start"
                aria-hidden="true"
                onPointerDown={(pointerEvent) => pointerDown(pointerEvent, event, "start")}
                onPointerMove={pointerMove}
                onPointerUp={pointerUp}
                onPointerCancel={cancelDrag}
              />
              <span
                className="cockpit-event__handle cockpit-event__handle--end"
                aria-hidden="true"
                onPointerDown={(pointerEvent) => pointerDown(pointerEvent, event, "end")}
                onPointerMove={pointerMove}
                onPointerUp={pointerUp}
                onPointerCancel={cancelDrag}
              />
              <button
                type="button"
                className="cockpit-event__menu-button"
                aria-label={`Actions pour ${catalogLabel(event)}`}
                aria-expanded={menuId === event.id}
                onClick={() => {
                  onSelect(event.id);
                  setMenuId(menuId === event.id ? null : event.id);
                }}
                disabled={disabled}
              >
                ⋮
              </button>

              {menuId === event.id ? (
                <div className="cockpit-event__menu" role="menu" aria-label="Actions de l'événement">
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      onToggle(event.id);
                      setMenuId(null);
                    }}
                  >
                    {disabledEvent ? "Activer" : "Désactiver"}
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      onDuplicate(event.id);
                      setMenuId(null);
                    }}
                  >
                    Dupliquer
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      onEdit(event.id);
                      setMenuId(null);
                    }}
                  >
                    Éditer
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    className="cockpit-event__danger"
                    onClick={() => {
                      onDelete(event.id);
                      setMenuId(null);
                    }}
                  >
                    Supprimer
                  </button>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      <div className="cockpit-timeline__months" aria-hidden="true">
        <span>M1</span>
        <span>M{Math.max(1, Math.round(horizon / 2))}</span>
        <span>M{Math.max(1, horizon)}</span>
      </div>

      {events.length > 0 ? (
        <p className="ui-muted cockpit-timeline__hint">
          Glissez un bloc pour le déplacer, ses bords pour la durée. Au clavier : ←/→ déplacer,
          Shift+←/→ durée, Alt+←/→ début, Entrée éditer, Suppr supprimer, Espace activer.
        </p>
      ) : null}

      {selectedId ? (
        <div className="cockpit-timeline__selection" aria-live="polite">
          <Badge tone="neutral">
            {events.find((event) => event.id === selectedId)?.enabled === false
              ? "Événement désactivé"
              : "Événement sélectionné"}
          </Badge>
        </div>
      ) : null}
    </section>
  );
}
