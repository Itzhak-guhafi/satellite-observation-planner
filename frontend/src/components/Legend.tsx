import type { PathOptions } from "leaflet";
import type { TargetInfo } from "../types";
import { markerStyle } from "./markerStyle";

const sample = (priority: number, opportunityCount = 1): TargetInfo => ({
  target_id: "",
  latitude: 0,
  longitude: 0,
  priority,
  opportunity_count: opportunityCount,
});

const ENTRIES: { label: string; target: TargetInfo; selected: boolean }[] = [
  ...[1, 2, 3, 4, 5].map((p) => ({ label: `P${p}${p === 1 ? " (highest)" : ""}`, target: sample(p), selected: true })),
  { label: "Not selected", target: sample(3), selected: false },
  { label: "No opportunities", target: sample(3, 0), selected: false },
];

/** Swatches are drawn with the same style function as the map markers, so they always match. */
export function Legend() {
  return (
    <div className="legend" aria-label="Legend">
      {ENTRIES.map(({ label, target, selected }) => (
        <div key={label} className="legend-row">
          <Swatch {...markerStyle(target, selected)} />
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}

function Swatch({ radius, path }: { radius: number; path: PathOptions }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <circle
        cx="9"
        cy="9"
        r={radius}
        stroke={path.color}
        strokeWidth={path.weight}
        strokeOpacity={path.opacity ?? 1}
        strokeDasharray={path.dashArray as string | undefined}
        fill={path.fillColor ?? "none"}
        fillOpacity={path.fillOpacity}
      />
    </svg>
  );
}
