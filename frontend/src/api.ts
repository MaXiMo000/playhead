const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;

// Sent on every request when configured. Note this key ships inside the
// built frontend bundle -- readable by anyone who loads the page -- which
// is why it's a proportionate mitigation for a single-user personal tool
// (stops opportunistic bots/scanners hitting an exposed API), not real
// authentication for a multi-user product. See backend/app/security.py.
function authHeaders(): HeadersInit {
  return API_KEY ? { Authorization: `Bearer ${API_KEY}` } : {};
}

export interface SessionSummary {
  session_id: string;
  event_count: number;
  started_at: number;
  ended_at: number;
}

// Claude Code's two shell tools: same command in, same stdout/stderr out.
export const isShell = (ev: { tool_name: string }) =>
  ev.tool_name === "Bash" || ev.tool_name === "PowerShell";

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
  is_anomalous: boolean;
}

export async function fetchSessions(): Promise<SessionSummary[]> {
  const res = await fetch(`${API_URL}/sessions`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`GET /sessions failed: ${res.status}`);
  return res.json();
}

export async function fetchSessionEvents(sessionId: string): Promise<PlayheadEvent[]> {
  const res = await fetch(`${API_URL}/sessions/${encodeURIComponent(sessionId)}/events`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`GET /sessions/${sessionId}/events failed: ${res.status}`);
  return res.json();
}
