import { useEffect, useMemo, useState } from "react";
import { fetchSessionEvents, fetchSessions, type PlayheadEvent, type SessionSummary } from "./api";
import DiffTheater from "./DiffTheater";
import TimelineCanvas from "./TimelineCanvas";
import TerminalStrip from "./TerminalStrip";

function activeEventIndex(events: PlayheadEvent[], playheadTs: number): number {
  if (events.length === 0) return -1;
  let idx = 0;
  for (let i = 0; i < events.length; i++) {
    if (events[i].ts_start <= playheadTs) idx = i;
  }
  return idx;
}

export default function App() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [events, setEvents] = useState<PlayheadEvent[]>([]);
  const [playheadTs, setPlayheadTs] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSessions()
      .then(setSessions)
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!selectedSession) return;
    fetchSessionEvents(selectedSession)
      .then((evs) => {
        setEvents(evs);
        setPlayheadTs(evs.length ? evs[0].ts_start : 0);
      })
      .catch((e) => setError(String(e)));
  }, [selectedSession]);

  const activeIdx = useMemo(() => activeEventIndex(events, playheadTs), [events, playheadTs]);
  const active = activeIdx >= 0 ? events[activeIdx] : null;

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <h1 style={{ fontSize: 20 }}>Playhead</h1>

      {error && <p style={{ color: "#f66" }}>{error}</p>}

      <section style={{ marginBottom: 24 }}>
        <label>
          Session:{" "}
          <select
            value={selectedSession ?? ""}
            onChange={(e) => setSelectedSession(e.target.value || null)}
          >
            <option value="">-- pick a session --</option>
            {sessions.map((s) => (
              <option key={s.session_id} value={s.session_id}>
                {s.session_id} ({s.event_count} events)
              </option>
            ))}
          </select>
        </label>
      </section>

      {events.length > 0 && (
        <>
          <section style={{ marginBottom: 16 }}>
            <TimelineCanvas events={events} playheadTs={playheadTs} onScrub={setPlayheadTs} />
          </section>

          <section style={{ marginBottom: 24 }}>
            <TerminalStrip events={events} playheadTs={playheadTs} />
          </section>

          {active && (
            <section>
              <h2 style={{ fontSize: 14 }}>
                {active.tool_name} — {active.file_path ?? active.bash_command}
              </h2>
              <p style={{ fontSize: 12, opacity: 0.7 }}>
                success: {String(active.tool_reported_success)}
              </p>
              {active.tool_name === "Bash" ? (
                <pre style={paneStyle}>{active.bash_output ?? "(no output)"}</pre>
              ) : (
                <DiffTheater
                  before={active.before_content}
                  after={active.after_content}
                  eventKey={active.tool_use_id}
                />
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}

const paneStyle: React.CSSProperties = {
  background: "#1a1a1a",
  padding: 12,
  borderRadius: 4,
  fontSize: 12,
  overflow: "auto",
  maxHeight: 400,
  whiteSpace: "pre-wrap",
};
