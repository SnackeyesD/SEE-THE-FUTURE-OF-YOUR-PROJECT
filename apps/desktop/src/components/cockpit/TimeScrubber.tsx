import { Button } from "@see/ui";

const QUARTER = 3;

function quarterTicks(horizon: number): number[] {
  const ticks: number[] = [];
  for (let month = 1; month <= horizon; month += QUARTER) ticks.push(month);
  if (horizon > 0 && ticks[ticks.length - 1] !== horizon) ticks.push(horizon);
  return ticks;
}

/**
 * Curseur de temps du cockpit.
 *
 * L'état du mois vit dans le store (`selection.month`) : ce composant ne
 * calcule rien, il déplace la sélection. Un `input[type=range]` fournit
 * nativement les flèches, `Home`/`End` et les lecteurs d'écran ; les ticks
 * trimestriels sont de vrais boutons pour sauter sans glisser.
 */
export function TimeScrubber({
  month,
  horizon,
  playing,
  disabled = false,
  onMonthChange,
  onTogglePlay,
}: {
  month: number | null;
  horizon: number;
  playing: boolean;
  disabled?: boolean;
  onMonthChange: (month: number) => void;
  onTogglePlay: () => void;
}) {
  const current = month !== null && month >= 1 && month <= horizon ? month : horizon > 0 ? 1 : 0;
  const ticks = quarterTicks(horizon);
  const calendarMonth = current > 0 ? ((current - 1) % 12) + 1 : null;

  return (
    <div className="cockpit-scrubber">
      <div className="cockpit-scrubber__head">
        <Button
          variant="secondary"
          size="small"
          aria-pressed={playing}
          onClick={onTogglePlay}
          disabled={disabled || horizon <= 0}
          title="Lecture mois par mois (Espace)"
        >
          {playing ? "Pause" : "Lecture"}
        </Button>
        <output className="cockpit-scrubber__value" htmlFor="cockpit-month">
          Mois {current > 0 ? current : "—"}
          {horizon > 0 ? ` / ${horizon}` : ""}
          {calendarMonth ? <span className="ui-muted"> · M{calendarMonth} de l'année</span> : null}
        </output>
      </div>

      <input
        id="cockpit-month"
        className="cockpit-scrubber__range"
        type="range"
        min={1}
        max={Math.max(1, horizon)}
        step={1}
        value={Math.max(1, current)}
        disabled={disabled || horizon <= 0}
        aria-label="Mois sélectionné"
        aria-valuetext={current > 0 ? `Mois ${current} sur ${horizon}` : "Aucun résultat"}
        onChange={(event) => onMonthChange(Number(event.target.value))}
      />

      <div className="cockpit-scrubber__ticks" role="group" aria-label="Jalons trimestriels">
        {ticks.map((tick) => (
          <button
            key={tick}
            type="button"
            className="cockpit-scrubber__tick"
            aria-pressed={tick === current}
            disabled={disabled}
            onClick={() => onMonthChange(tick)}
            title={`Aller au mois ${tick}`}
          >
            {tick}
          </button>
        ))}
      </div>
    </div>
  );
}
