import type { PathOptions } from "leaflet";
import { NO_OPPORTUNITY_COLOR, PRIORITY_COLORS } from "../priorities";
import type { TargetInfo } from "../types";

/** Single source of marker appearance, shared by the map and the legend. */
export function markerStyle(target: TargetInfo, selected: boolean): { radius: number; path: PathOptions } {
  if (target.opportunity_count === 0) {
    return { radius: 4, path: { color: NO_OPPORTUNITY_COLOR, weight: 1, dashArray: "2 3", fillOpacity: 0 } };
  }
  const color = PRIORITY_COLORS[target.priority];
  return selected
    ? { radius: 7, path: { color: "#f1f5f9", weight: 1.5, fillColor: color, fillOpacity: 0.95 } }
    : { radius: 5, path: { color, weight: 1.5, opacity: 0.85, fillColor: color, fillOpacity: 0.15 } };
}
