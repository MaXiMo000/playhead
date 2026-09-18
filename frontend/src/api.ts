const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface SessionSummary {
  session_id: string;
  event_count: number;
  started_at: number;
  ended_at: number;
}

export interface PlayheadEvent {
  id: number;
  session_id: string | null;
  tool_use_id: string;
  tool_name: string;
  ts_start: number;
  ts_end: number;
  cwd: string | null;
  file_path: string | null;
  before_content: string | null;
  after_content: string | null;
  bash_command: string | null;
  bash_output: string | null;
  tool_reported_success: boolean | null;
}

export async function fetchSessions(): Promise<SessionSummary[]> {
  const res = await fetch(`${API_URL}/sessions`);
  if (!res.ok) throw new Error(`GET /sessions failed: ${res.status}`);
  return res.json();
}

export async function fetchSessionEvents(sessionId: string): Promise<PlayheadEvent[]> {
  const res = await fetch(`${API_URL}/sessions/${encodeURIComponent(sessionId)}/events`);
  if (!res.ok) throw new Error(`GET /sessions/${sessionId}/events failed: ${res.status}`);
  return res.json();
}
