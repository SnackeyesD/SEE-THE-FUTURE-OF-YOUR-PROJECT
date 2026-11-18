import { Button } from "@see/ui";

export function randomSeed(): number {
  return 1 + Math.floor(Math.random() * 999_999);
}

/**
 * Graine toujours visible : saisie directe ou tirage d'une autre graine.
 * La graine est une entrée de simulation, donc annulable via le store.
 */
export function SeedControl({
  seed,
  disabled = false,
  onChange,
  onReroll,
}: {
  seed: number;
  disabled?: boolean;
  onChange: (seed: number) => void;
  onReroll?: () => void;
}) {
  return (
    <div className="seed-control">
      <label className="seed-control__label" htmlFor="cockpit-seed">
        Graine
      </label>
      <input
        id="cockpit-seed"
        className="seed-control__input"
        type="number"
        inputMode="numeric"
        value={seed}
        disabled={disabled}
        onChange={(event) => {
          const next = Number(event.target.value);
          if (Number.isFinite(next)) onChange(Math.trunc(next));
        }}
      />
      <Button
        variant="ghost"
        size="small"
        disabled={disabled}
        onClick={onReroll ?? (() => onChange(randomSeed()))}
      >
        Autre graine
      </Button>
    </div>
  );
}
