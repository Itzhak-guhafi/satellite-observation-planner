import type { PlanExport, ProgressEvent, ScenarioOverview } from "./types";

export async function fetchScenario(): Promise<ScenarioOverview> {
  const response = await fetch("/api/scenario");
  if (!response.ok) throw new Error(`Failed to load scenario (HTTP ${response.status})`);
  return response.json() as Promise<ScenarioOverview>;
}

interface StreamHandlers {
  onProgress: (event: ProgressEvent) => void;
  onDone: (plan: PlanExport) => void;
  onFailed: (message: string) => void;
}

/** Opens the live planning stream; the server starts planning on connect. Returns a close function. */
export function streamPlan({ onProgress, onDone, onFailed }: StreamHandlers): () => void {
  const source = new EventSource("/api/plan/stream");
  const parse = <T>(event: Event): T => JSON.parse((event as MessageEvent<string>).data) as T;

  source.addEventListener("progress", (event) => onProgress(parse<ProgressEvent>(event)));
  source.addEventListener("done", (event) => {
    // Close before the server ends the response, otherwise EventSource reconnects and plans again.
    source.close();
    onDone(parse<PlanExport>(event));
  });
  source.addEventListener("failed", (event) => {
    source.close();
    onFailed(parse<{ message: string }>(event).message);
  });
  source.onerror = () => {
    source.close();
    onFailed("Connection to the planner was lost");
  };
  return () => source.close();
}

export function downloadJson(data: unknown, filename: string): void {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const link = Object.assign(document.createElement("a"), { href: url, download: filename });
  link.click();
  URL.revokeObjectURL(url);
}
