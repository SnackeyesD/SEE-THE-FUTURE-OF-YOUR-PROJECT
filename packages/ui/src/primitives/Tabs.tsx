import { useRef, type KeyboardEvent } from "react";
import { cx } from "../cx";

export type TabItem = {
  id: string;
  label: string;
};

/**
 * Onglets contrôlés, accessibles au clavier :
 * rôle `tablist`/`tab`, `aria-selected`, navigation ←/→, Home/End.
 * L'onglet actif utilise `--accent` (interactif) — jamais une série.
 */
export function Tabs({
  items,
  value,
  onChange,
  ariaLabel,
  className,
}: {
  items: TabItem[];
  value: string;
  onChange: (id: string) => void;
  ariaLabel: string;
  className?: string;
}) {
  const listRef = useRef<HTMLDivElement>(null);

  const move = (from: number, delta: number) => {
    const next = (from + delta + items.length) % items.length;
    onChange(items[next].id);
    const buttons = listRef.current?.querySelectorAll<HTMLButtonElement>(".ui-tab");
    buttons?.[next]?.focus();
  };

  const handleKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (event.key === "ArrowRight") {
      event.preventDefault();
      move(index, 1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      move(index, -1);
    } else if (event.key === "Home") {
      event.preventDefault();
      onChange(items[0].id);
      listRef.current?.querySelectorAll<HTMLButtonElement>(".ui-tab")[0]?.focus();
    } else if (event.key === "End") {
      event.preventDefault();
      onChange(items[items.length - 1].id);
      listRef.current
        ?.querySelectorAll<HTMLButtonElement>(".ui-tab")
        [items.length - 1]?.focus();
    }
  };

  return (
    <div className={cx("ui-tabs", className)} role="tablist" aria-label={ariaLabel} ref={listRef}>
      {items.map((item, index) => (
        <button
          key={item.id}
          type="button"
          role="tab"
          aria-selected={item.id === value}
          tabIndex={item.id === value ? 0 : -1}
          className={cx("ui-tab", item.id === value && "ui-tab--active")}
          onClick={() => onChange(item.id)}
          onKeyDown={(event) => handleKey(event, index)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
