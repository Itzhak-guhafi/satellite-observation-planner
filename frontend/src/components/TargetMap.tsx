import type { LatLngBoundsExpression, Map as LeafletMap } from "leaflet";
import { memo, useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import type { TargetInfo } from "../types";
import { Legend } from "./Legend";
import { markerStyle } from "./markerStyle";

interface TargetMapProps {
  targets: TargetInfo[];
  selectedByTarget: ReadonlyMap<string, string>;
}

/**
 * The map is created once and never re-centred by planning updates, so the user can pan and zoom
 * freely while the stream runs. Only markers whose selection changed re-render (see TargetMarker).
 */
export function TargetMap({ targets, selectedByTarget }: TargetMapProps) {
  const [map, setMap] = useState<LeafletMap | null>(null);
  const bounds = useMemo<LatLngBoundsExpression>(
    () => targets.map((t) => [t.latitude, t.longitude] as [number, number]),
    [targets],
  );

  useEffect(() => {
    map?.fitBounds(bounds, { padding: [24, 24] });
  }, [map, bounds]);

  return (
    <div className="map-wrapper">
      <MapContainer ref={setMap} center={[20, 20]} zoom={2} minZoom={2} worldCopyJump className="map">
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          maxZoom={19}
        />
        {targets.map((target) => (
          <TargetMarker key={target.target_id} target={target} selectedOpportunityId={selectedByTarget.get(target.target_id)} />
        ))}
      </MapContainer>
      <button type="button" className="fit-button" onClick={() => map?.fitBounds(bounds, { padding: [24, 24] })}>
        Fit to targets
      </button>
      <Legend />
    </div>
  );
}

interface TargetMarkerProps {
  target: TargetInfo;
  selectedOpportunityId: string | undefined;
}

const TargetMarker = memo(function TargetMarker({ target, selectedOpportunityId }: TargetMarkerProps) {
  const center = useMemo<[number, number]>(() => [target.latitude, target.longitude], [target]);
  const style = markerStyle(target, selectedOpportunityId !== undefined);
  const status =
    target.opportunity_count === 0 ? "no opportunities" : (selectedOpportunityId ?? "not selected");

  return (
    <CircleMarker center={center} radius={style.radius} pathOptions={style.path}>
      <Tooltip>
        {target.target_id} · P{target.priority} · {status}
      </Tooltip>
    </CircleMarker>
  );
});
