import type {
  SimulationRunParamsResult,
  SimulationTrajectoriesResult,
  SurfaceMetric,
} from "@see/protocol";
import { Button, InlineAlert } from "@see/ui";
import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type RefObject,
} from "react";

import { formatCurrency, formatNumber } from "../../lib/format";
import { getRunParams, getTrajectories } from "../../lib/ipc";
import { formatMetricValue, surfaceMetricSpec } from "../../lib/metrics";
import { buildPointCloud, type PointCloudGeometry } from "../../lib/pointCloud";
import {
  buildSurfaceGeometry,
  surfaceMarker,
  type SurfaceMarker,
} from "../../lib/surface3d";
import { detectWebGL, isSlow, type WebGLFailureReason, type WebGLStatus } from "../../lib/webgl";

const Scene3D = lazy(() => import("./Scene3D"));

export type Surface3DMode = "surface" | "cloud";

export interface Surface3DViewProps {
  /** Run final courant ; `null` désactive le nuage Monte Carlo. */
  runId: string | null;
  xValues: number[];
  yValues: number[];
  z: Array<Array<number | null>>;
  current: number[] | null;
  metric: SurfaceMetric;
  xLabel: string;
  yLabel: string;
  currency?: string;
  onPick: (x: number, y: number) => void;
  onFallback: (reason: WebGLFailureReason) => void;
}

type TrajectoryState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; data: SimulationTrajectoriesResult }
  | { status: "error"; message: string };

function useOnScreen<T extends Element>(): [RefObject<T>, boolean] {
  const ref = useRef<T>(null);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const element = ref.current;
    if (!element || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (entry) setVisible(entry.isIntersecting);
      },
      { rootMargin: "120px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return [ref, visible];
}

function hoverLabel(
  point: PointCloudGeometry["points"][number],
  currency: string,
): string {
  const breakEven =
    point.breakEvenMonth === null ? "point mort non atteint" : `point mort ${point.breakEvenMonth} mois`;
  return `Run ${point.index + 1} · ${breakEven} · profit final ${formatCurrency(
    point.finalProfit,
    currency,
  )}`;
}

/**
 * Enveloppe accessible de la 3D : bascule surface/nuage, détection WebGL,
 * avertissement de lenteur, légende HTML et repli 2D. Three.js n'est chargé
 * qu'ici, via `lazy`, donc jamais au démarrage de l'application.
 */
export function Surface3DView({
  runId,
  xValues,
  yValues,
  z,
  current,
  metric,
  xLabel,
  yLabel,
  currency = "XOF",
  onPick,
  onFallback,
}: Surface3DViewProps) {
  const [status] = useState<WebGLStatus>(() => detectWebGL());
  const [mode, setMode] = useState<Surface3DMode>("surface");
  const [resetToken, setResetToken] = useState(0);
  const [topDown, setTopDown] = useState(false);
  const [hoverCell, setHoverCell] = useState<{ column: number; row: number } | null>(null);
  const [hoverPoint, setHoverPoint] = useState<number | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [params, setParams] = useState<SimulationRunParamsResult | null>(null);
  const [paramsError, setParamsError] = useState<string | null>(null);
  const [frameRate, setFrameRate] = useState<number | null>(null);
  const [slowDismissed, setSlowDismissed] = useState(false);
  const [trajectories, setTrajectories] = useState<TrajectoryState>({ status: "idle" });
  const [containerRef, visible] = useOnScreen<HTMLDivElement>();

  const spec = surfaceMetricSpec(metric);
  const geometry = useMemo(
    () =>
      buildSurfaceGeometry({
        xValues,
        yValues,
        z,
        lowerIsBetter: spec.lowerIsBetter,
      }),
    [spec.lowerIsBetter, xValues, yValues, z],
  );
  const marker: SurfaceMarker | null = useMemo(
    () =>
      surfaceMarker(current as [number, number] | null, {
        xValues,
        yValues,
        z,
        lowerIsBetter: spec.lowerIsBetter,
      }),
    [current, spec.lowerIsBetter, xValues, yValues, z],
  );
  const cloud = useMemo<PointCloudGeometry | null>(
    () =>
      trajectories.status === "ready"
        ? buildPointCloud({
            trajectories: trajectories.data.trajectories,
            horizonMonths: trajectories.data.horizonMonths,
          })
        : null,
    [trajectories],
  );

  useEffect(() => {
    if (!status.supported) onFallback(status.reason ?? "no_context");
  }, [onFallback, status.reason, status.supported]);

  const generation = useRef(0);

  useEffect(() => {
    if (mode !== "cloud" || !runId) return;
    const current = ++generation.current;
    setTrajectories({ status: "loading" });
    void getTrajectories({ runId, count: 200 })
      .then((data) => {
        if (generation.current === current) setTrajectories({ status: "ready", data });
      })
      .catch((reason: unknown) => {
        if (generation.current === current) {
          setTrajectories({
            status: "error",
            message: reason instanceof Error ? reason.message : String(reason),
          });
        }
      });
  }, [mode, runId]);

  const handleContextLost = useCallback(() => {
    onFallback("context_lost");
  }, [onFallback]);

  const handleFrameRate = useCallback((fps: number) => {
    setFrameRate(fps);
  }, []);

  const handlePickCell = useCallback(
    (column: number, row: number) => {
      const x = xValues[column];
      const y = yValues[row];
      if (x === undefined || y === undefined) return;
      onPick(x, y);
    },
    [onPick, xValues, yValues],
  );

  const selectRun = useCallback(
    (position: number) => {
      if (!runId || !cloud) return;
      const point = cloud.points[position];
      if (!point) return;
      setSelectedIndex(position);
      setParams(null);
      setParamsError(null);
      void getRunParams({ runId, index: point.index })
        .then(setParams)
        .catch((reason: unknown) => {
          setParamsError(reason instanceof Error ? reason.message : String(reason));
        });
    },
    [cloud, runId],
  );

  const cloudUnavailable = !runId;
  const slow = !slowDismissed && frameRate !== null && isSlow(frameRate);

  if (!status.supported) {
    return (
      <InlineAlert tone="neutral" title="Vue 3D indisponible">
        {status.reason === "context_lost"
          ? "Le contexte WebGL a été perdu : la carte 2D prend le relais."
          : "WebGL n'est pas disponible sur cette machine : la carte 2D et son tableau restent la référence."}
      </InlineAlert>
    );
  }

  const hoveredCell = hoverCell
    ? {
        x: xValues[hoverCell.column],
        y: yValues[hoverCell.row],
        value: z[hoverCell.row]?.[hoverCell.column],
      }
    : null;
  const hoveredPoint =
    mode === "cloud" && hoverPoint !== null && cloud
      ? cloud.points[hoverPoint]
      : null;

  return (
    <figure className="surface3d" aria-label={`Vue 3D — ${spec.label} selon ${xLabel} et ${yLabel}`}>
      <div className="surface3d__toolbar">
        <div className="surface3d__modes" role="group" aria-label="Vue 3D">
          <Button
            size="small"
            variant={mode === "surface" ? "secondary" : "ghost"}
            aria-pressed={mode === "surface"}
            onClick={() => setMode("surface")}
          >
            Surface 3D
          </Button>
          <Button
            size="small"
            variant={mode === "cloud" ? "secondary" : "ghost"}
            aria-pressed={mode === "cloud"}
            disabled={cloudUnavailable}
            title={
              cloudUnavailable
                ? "Lancez un calcul final pour explorer les runs."
                : undefined
            }
            onClick={() => setMode("cloud")}
          >
            Nuage Monte Carlo
          </Button>
        </div>
        <div className="surface3d__camera">
          <Button size="small" variant="ghost" onClick={() => setResetToken((value) => value + 1)}>
            Réinitialiser
          </Button>
          <Button
            size="small"
            variant={topDown ? "secondary" : "ghost"}
            aria-pressed={topDown}
            onClick={() => setTopDown((value) => !value)}
          >
            Vue du dessus
          </Button>
          <Button size="small" variant="ghost" onClick={() => onFallback("slow")}>
            Revenir à la carte 2D
          </Button>
        </div>
      </div>

      {slow ? (
        <InlineAlert tone="warn" title="Rendu 3D lent">
          {`Médiane mesurée : ${formatNumber(frameRate ?? 0, 0)} fps. Vous pouvez rester en 3D ou revenir à la carte 2D ; le repli n'est jamais imposé.`}{" "}
          <Button size="small" variant="ghost" onClick={() => setSlowDismissed(true)}>
            Continuer en 3D
          </Button>
        </InlineAlert>
      ) : null}

      {cloudUnavailable && mode === "cloud" ? (
        <InlineAlert tone="neutral" title="Nuage indisponible">
          Aucun run final n'est disponible dans cette session. Lancez un calcul final
          pour explorer les trajectoires ; aucun nuage n'est inventé.
        </InlineAlert>
      ) : null}

      <div
        className="surface3d__stage"
        ref={containerRef}
        data-visible={visible ? "true" : "false"}
      >
        {visible ? (
          <Suspense
            fallback={
              <p className="ui-muted" role="status">
                Chargement du moteur 3D…
              </p>
            }
          >
            <Scene3D
              geometry={geometry}
              xValues={xValues}
              yValues={yValues}
              marker={marker}
              cloud={mode === "cloud" ? cloud : null}
              mode={mode}
              resetToken={resetToken}
              topDown={topDown}
              onPickCell={handlePickCell}
              onHoverCell={setHoverCell}
              onPickPoint={selectRun}
              onHoverPoint={setHoverPoint}
              onContextLost={handleContextLost}
              onFrameRate={handleFrameRate}
            />
          </Suspense>
        ) : (
          <p className="ui-muted">
            Rendu 3D suspendu : le panneau n'est pas visible à l'écran.
          </p>
        )}

        <div className="surface3d__legend" aria-hidden="true">
          <span className="surface3d__legend-label">{spec.label}</span>
          <span className="surface3d__legend-scale">
            {Array.from({ length: 5 }, (_, index) => (
              <span key={index} className="surface3d__swatch" style={{ background: `var(--heat-${index})` }} />
            ))}
          </span>
          <span className="surface3d__range">
            {formatMetricValue(metric, geometry.minimum, currency)} →{" "}
            {formatMetricValue(metric, geometry.maximum, currency)}
          </span>
        </div>

        <div className="surface3d__axes" aria-hidden="true">
          <span>X · {xLabel}</span>
          <span>Y · {yLabel}</span>
          <span>Z · {spec.label}</span>
        </div>
      </div>

      <figcaption className="surface3d__caption">
        {mode === "surface" ? (
          <span>
            {`${geometry.renderedCellCount} cellule(s) affichée(s) sur ${geometry.cellCount}. Cliquez la surface pour appliquer ${xLabel} et ${yLabel} au scénario.`}
          </span>
        ) : (
          <span>
            {trajectories.status === "ready"
              ? `${trajectories.data.trajectories.length} trajectoire(s) sur ${formatNumber(
                  trajectories.data.runs,
                )} runs ; ${formatNumber(trajectories.data.runsRetained)} retenue(s).`
              : "Chargement des trajectoires du run final…"}
          </span>
        )}{" "}
        <span className="ui-muted">
          La carte 2D et son tableau restent disponibles à tout moment.
        </span>
      </figcaption>

      {trajectories.status === "loading" ? (
        <p className="ui-muted" role="status">
          Lecture des trajectoires via le moteur…
        </p>
      ) : null}
      {trajectories.status === "error" ? (
        <InlineAlert tone="danger" title="Trajectoires indisponibles">
          {trajectories.message}
        </InlineAlert>
      ) : null}
      {trajectories.status === "ready" && trajectories.data.truncated ? (
        <p className="ui-muted">
          Échantillon borné à {trajectories.data.trajectories.length} trajectoires (phase 12) :
          le nuage ne prétend pas représenter chaque run.
        </p>
      ) : null}
      {mode === "cloud" && trajectories.status === "ready" ? (
        <p className="ui-muted">
          Axes : X = besoin de financement (trésorerie minimale), Y = mois de point
          mort, Z = profit final cumulé. Valeurs dérivées des trajectoires du moteur.
        </p>
      ) : null}

      <p className="ui-muted surface3d__hover" role="status">
        {mode === "surface"
          ? hoveredCell && hoveredCell.x !== undefined && hoveredCell.y !== undefined
            ? `${xLabel} = ${formatNumber(hoveredCell.x, 4)} · ${yLabel} = ${formatNumber(
                hoveredCell.y,
                4,
              )} · ${spec.label} = ${
                typeof hoveredCell.value === "number"
                  ? formatMetricValue(metric, hoveredCell.value, currency)
                  : "en attente"
              }`
            : "Survolez la surface pour lire les valeurs."
          : hoveredPoint
            ? hoverLabel(hoveredPoint, currency)
            : "Survolez un point pour lire le run ; cliquez pour ses paramètres."}
      </p>

      {selectedIndex !== null && cloud ? (
        <section className="surface3d__selection" aria-label="Run sélectionné">
          <h3>Run sélectionné</h3>
          {paramsError ? (
            <InlineAlert tone="danger" title="Paramètres indisponibles">
              {paramsError}
            </InlineAlert>
          ) : params ? (
            <dl className="surface3d__params">
              {Object.entries(params.parameters).map(([key, value]) => (
                <div key={key}>
                  <dt>{key}</dt>
                  <dd>{formatNumber(value, 4)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="ui-muted" role="status">
              Lecture des paramètres du run…
            </p>
          )}
          <p className="ui-muted">
            {hoverLabel(cloud.points[selectedIndex], currency)} · run #
            {params?.index ?? cloud.points[selectedIndex]?.index}
          </p>
        </section>
      ) : null}

      <p className="ui-muted">
        Graine et version moteur sont affichées dans la comparaison ; la 3D ne
        modifie aucune valeur sans votre clic.
      </p>
    </figure>
  );
}
