import { useMemo, useState } from "react";
import type { SessionSummary } from "./api";
import "./SessionList.css";

interface Props {
  sessions: SessionSummary[];
  selectedSession: string | null;
  onSelect: (sessionId: string) => void;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${Math.round(seconds % 60)}s`;
}

// Replaces the plain <select> from step 8a now that there's more than a
// handful of sessions to pick from -- a searchable list with real metadata
// (event count, when, how long) instead of an unlabeled id in a dropdown.
export default function SessionList({ sessions, selectedSession, onSelect }: Props) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return sessions;
    return sessions.filter((s) => s.session_id.toLowerCase().includes(q));
  }, [sessions, query]);

  return (
    <div>
      <input
        className="session-list-search"
        placeholder="Search sessions..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div className="session-list">
        {filtered.length === 0 && <div className="session-list-empty">No sessions match.</div>}
        {filtered.map((s) => (
          <div
            key={s.session_id}
            className={`session-list-row${s.session_id === selectedSession ? " selected" : ""}`}
            onClick={() => onSelect(s.session_id)}
          >
            <span className="session-list-row-id">{s.session_id}</span>
            <span className="session-list-row-meta">
              {new Date(s.started_at * 1000).toLocaleString()} · {s.event_count} events ·{" "}
              {formatDuration(s.ended_at - s.started_at)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
