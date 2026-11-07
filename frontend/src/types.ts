export type PriorityKey = "P1" | "P2" | "P3" | "P4" | "P5";
export type CountsByPriority = Record<PriorityKey, number>;

export interface TargetInfo {
  target_id: string;
  latitude: number;
  longitude: number;
  priority: number;
  opportunity_count: number;
}

export interface OpportunityInfo {
  opportunity_id: string;
  target_id: string;
  start_utc: string;
  end_utc: string;
}

export interface ScenarioOverview {
  scenario_id: string;
  satellite_id: string;
  horizon: { start_utc: string; end_utc: string };
  targets: TargetInfo[];
  opportunities: OpportunityInfo[];
}

export interface ProgressEvent {
  opportunity_ids: string[];
  counts_by_priority: CountsByPriority;
  phase: "construction" | "improvement" | "completed";
  passes: number;
  elapsed_seconds: number;
}

export interface ScheduleEntry {
  sequence: number;
  opportunity_id: string;
  target_id: string;
  priority: number;
  latitude: number;
  longitude: number;
  start_utc: string;
  end_utc: string;
  transition_from_previous_seconds: number | null;
}

export interface PlanExport {
  scenario_id: string;
  satellite_id: string;
  horizon: { start_utc: string; end_utc: string };
  summary: {
    selected_count: number;
    counts_by_priority: CountsByPriority;
    computation_duration_seconds: number;
    algorithm: string;
    stop_reason: string;
    improvement_passes: number;
  };
  schedule: ScheduleEntry[];
}

export type RunStatus = "idle" | "running" | "completed" | "failed";
