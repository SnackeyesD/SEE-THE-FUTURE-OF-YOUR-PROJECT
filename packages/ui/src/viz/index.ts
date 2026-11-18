/**
 * Composants de visualisation « Ink & Signal » (refont phase 04).
 * Sans dépendance métier : les formats/labels arrivent par props.
 */
export { LineChart, type LinePoint, type LineSeries } from "./LineChart";
export { Histogram, type VizBin, type PercentileMark } from "./Histogram";
export { BarChart, type BarCategory } from "./BarChart";
export { DivergingBars, type DivergingRow } from "./DivergingBars";
export { Sparkline } from "./Sparkline";
export { FanChart, type FanChartProps, type FanThreshold } from "./FanChart";
export {
  cdfProbabilityAt,
  fanBandPath,
  fanDomain,
  fanLinePath,
  nearestMonth,
  normalizeCdf,
  normalizeFanPoints,
  thresholdStep,
} from "./fan";
export type { CashCdfPoint, Domain, FanPoint, GhostSeries } from "./fan";
export { Legend, type LegendItem } from "./Legend";
export { scale, niceTicks, serieStyle } from "./scale";
