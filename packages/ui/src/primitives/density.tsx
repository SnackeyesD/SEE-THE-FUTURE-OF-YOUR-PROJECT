import { createContext, useContext, type ReactNode } from "react";

/**
 * Densité globale des composants (comfortable | compact).
 * Consommé par Button et les composants denses (tables, listes).
 */
const DensityContext = createContext<"comfortable" | "compact">("comfortable");

export function DensityProvider({
  value,
  children,
}: {
  value: "comfortable" | "compact";
  children: ReactNode;
}) {
  return <DensityContext.Provider value={value}>{children}</DensityContext.Provider>;
}

export function useDensity() {
  return useContext(DensityContext);
}
