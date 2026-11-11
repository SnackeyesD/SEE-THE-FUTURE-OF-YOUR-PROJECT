// Tokens « Ink & Signal » + polices embarquées : chaque consommateur de
// @see/ui charge automatiquement la source de vérité visuelle (refont phase 02).
import "./tokens.css";
import "./primitives.css";
import "./viz/chart.css";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "@fontsource/jetbrains-mono/600.css";

export { UI_VERSION, cx } from "./cx";
export { ink, line, text, signals, code, SERIES, seriesColor, seriesFill } from "./tokens";
export {
  DensityProvider,
  useDensity,
  Button,
  Badge,
  Card,
  CardHeader,
  Field,
  SelectField,
  TextareaField,
  InlineAlert,
  Stat,
  EmptyState,
  ProgressBar,
  Tabs,
  Table,
} from "./components";
export type { ButtonVariant, BadgeTone, AlertTone, AlertAction, StatTone, TabItem, TableColumn } from "./components";
export {
  LineChart,
  Histogram,
  BarChart,
  DivergingBars,
  Sparkline,
  Legend,
  scale,
  niceTicks,
  serieStyle,
} from "./viz";
export type {
  LinePoint,
  LineSeries,
  VizBin,
  PercentileMark,
  BarCategory,
  DivergingRow,
  LegendItem,
} from "./viz";
