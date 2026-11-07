import { PRIORITY_COLORS, PRIORITY_KEYS } from "../priorities";
import type { CountsByPriority, PlanExport, RunStatus, TargetInfo } from "../types";

interface ControlPanelProps {
  targets: TargetInfo[];
  status: RunStatus;
  counts: CountsByPriority | null;
  elapsedSeconds: number | null;
  plan: PlanExport | null;
  error: string | null;
  onStart: () => void;
  onReset: () => void;
  onDownload: () => void;
}

const STATUS_LABELS: Record<RunStatus, string> = {
  idle: "Idle",
  running: "Running…",
  completed: "Completed",
  failed: "Failed",
};

export function ControlPanel({ targets, status, counts, elapsedSeconds, plan, error, onStart, onReset, onDownload }: ControlPanelProps) {
  const schedulable = (p: number) => targets.filter((t) => t.priority === p && t.opportunity_count > 0).length;
  const total = (p: number) => targets.filter((t) => t.priority === p).length;

  return (
    <aside className="panel">
      <h1>Observation Planner</h1>

      <div className="actions">
        <button type="button" className="primary" onClick={onStart} disabled={status !== "idle"}>
          Start
        </button>
        <button type="button" onClick={onReset} disabled={status === "idle" || status === "running"}>
          Reset
        </button>
        <button type="button" onClick={onDownload} disabled={status !== "completed"}>
          Download plan.json
        </button>
      </div>

      <p className={`status status-${status}`}>
        <span className="status-dot" /> {STATUS_LABELS[status]}
        {elapsedSeconds !== null && <span className="muted"> · {(elapsedSeconds * 1000).toFixed(0)} ms</span>}
      </p>
      {error && <p className="error">{error}</p>}

      <table className="counts">
        <thead>
          <tr>
            <th>Priority</th>
            <th>Selected</th>
            <th title="Targets that have at least one opportunity">Schedulable</th>
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {PRIORITY_KEYS.map((key, i) => (
            <tr key={key}>
              <td>
                <span className="dot" style={{ background: PRIORITY_COLORS[i + 1] }} /> {key}
              </td>
              <td className="num strong">{counts?.[key] ?? 0}</td>
              <td className="num">{schedulable(i + 1)}</td>
              <td className="num muted">{total(i + 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {plan && (
        <section className="schedule">
          <h2>
            Schedule <span className="muted">({plan.summary.selected_count} observations, {plan.summary.stop_reason})</span>
          </h2>
          <ol>
            {plan.schedule.map((entry) => (
              <li key={entry.opportunity_id}>
                <span className="time">{entry.start_utc.slice(11, 19)}</span>
                <span className="dot" style={{ background: PRIORITY_COLORS[entry.priority] }} />
                {entry.target_id} <span className="muted">P{entry.priority}</span>
              </li>
            ))}
          </ol>
        </section>
      )}
    </aside>
  );
}
