/**
 * Barrel des primitives — compatibilité avec les imports existants
 * (`@see/ui`). Les implémentations vivent dans primitives/.
 */
export { DensityProvider, useDensity } from "./primitives/density";
export { Button, type ButtonVariant } from "./primitives/Button";
export { Badge, type BadgeTone } from "./primitives/Badge";
export { Card, CardHeader } from "./primitives/Card";
export { Field, SelectField, TextareaField } from "./primitives/Field";
export { InlineAlert, type AlertAction, type AlertTone } from "./primitives/Alert";
export { Stat, type StatTone } from "./primitives/Stat";
export { EmptyState } from "./primitives/Empty";
export { ProgressBar } from "./primitives/Progress";
export { Tabs, type TabItem } from "./primitives/Tabs";
export { Table, type TableColumn } from "./primitives/Table";
