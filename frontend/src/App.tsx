import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { downloadJson, fetchScenario, streamPlan } from "./api";
import { ControlPanel } from "./components/ControlPanel";
import { TargetMap } from "./components/TargetMap";
import type { CountsByPriority, PlanExport, RunStatus, ScenarioOverview } from "./types";

export function App() {
  const [scenario, setScenario] = useState<ScenarioOverview | null>(null);
  const [status, setStatus] = useState<RunStatus>("idle");
  const [selectedIds, setSelectedIds] = useState<readonly string[]>([]);
  const [counts, setCounts] = useState<CountsByPriority | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState<number | null>(null);
  const [plan, setPlan] = useState<PlanExport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const closeStream = useRef<(() => void) | null>(null);

  useEffect(() => {
    fetchScenario().then(setScenario, (e: Error) => setError(e.message));
    return () => closeStream.current?.();
  }, []);

  const targetByOpportunity = useMemo(
    () => new Map(scenario?.opportunities.map((o) => [o.opportunity_id, o.target_id])),
    [scenario],
  );
  const selectedByTarget = useMemo(
    () => new Map(selectedIds.map((id) => [targetByOpportunity.get(id) ?? id, id])),
    [selectedIds, targetByOpportunity],
  );

  const reset = useCallback(() => {
    closeStream.current?.();
    setStatus("idle");
    setSelectedIds([]);
    setCounts(null);
    setElapsedSeconds(null);
    setPlan(null);
    setError(null);
  }, []);

  const start = useCallback(() => {
    reset();
    setStatus("running");
    closeStream.current = streamPlan({
      onProgress: (event) => {
        setSelectedIds(event.opportunity_ids);
        setCounts(event.counts_by_priority);
        setElapsedSeconds(event.elapsed_seconds);
      },
      onDone: (result) => {
        // The map, counters and download all come from this one object: the exported plan is the plan shown.
        setPlan(result);
        setSelectedIds(result.schedule.map((entry) => entry.opportunity_id));
        setCounts(result.summary.counts_by_priority);
        setElapsedSeconds(result.summary.computation_duration_seconds);
        setStatus("completed");
      },
      onFailed: (message) => {
        setError(message);
        setStatus("failed");
      },
    });
  }, [reset]);

  const download = useCallback(() => plan && downloadJson(plan, "plan.json"), [plan]);

  if (!scenario) {
    return <div className="loading">{error ?? "Loading scenario…"}</div>;
  }

  return (
    <div className="layout">
      <ControlPanel
        targets={scenario.targets}
        status={status}
        counts={counts}
        elapsedSeconds={elapsedSeconds}
        plan={plan}
        error={error}
        onStart={start}
        onReset={reset}
        onDownload={download}
      />
      <TargetMap targets={scenario.targets} selectedByTarget={selectedByTarget} />
    </div>
  );
}
