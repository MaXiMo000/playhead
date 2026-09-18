import { useEffect, useMemo, useState } from "react";
import { fetchSessionEvents, fetchSessions, type PlayheadEvent, type SessionSummary } from "./api";

// Deliberately the plainest possible version of the timeline: a single
// <input type=range> playhead over events placed by timestamp, no canvas,
// no styling beyond what's needed to read it. This exists to prove the
// data model (sessions -> ordered events -> a scrubbable position) supports
// the interaction before any time goes into the real multi-track canvas
// renderer, diff-theater morphing, or blast-radius map.

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

  const minTs = events[0]?.ts_start ?? 0;
  const maxTs = events[events.length - 1]?.ts_end ?? 1;
  const activeIdx = useMemo(() => activeEventIndex(events, playheadTs), [events, playheadTs]);
  const active = activeIdx >= 0 ? events[activeIdx] : null;

  return (
    <div style={{ padding: 24, maxWidth: 1000, margin: "0 auto" }}>
      <h1 style={{ fontSize: 20 }}>Playhead — flat timeline (step 8a)</h1>

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
            <input
              type="range"
              min={minTs}
              max={maxTs}
              step={(maxTs - minTs) / 1000 || 0.01}
              value={playheadTs}
              onChange={(e) => setPlayheadTs(Number(e.target.value))}
              style={{ width: "100%" }}
            />
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, opacity: 0.6 }}>
              <span>{new Date(minTs * 1000).toLocaleTimeString()}</span>
              <span>{new Date(maxTs * 1000).toLocaleTimeString()}</span>
            </div>
          </section>

          <section style={{ display: "flex", gap: 4, marginBottom: 24, flexWrap: "wrap" }}>
            {events.map((ev, i) => (
              <div
                key={ev.tool_use_id}
                onClick={() => setPlayheadTs(ev.ts_start)}
                style={{
                  padding: "4px 8px",
                  fontSize: 11,
                  cursor: "pointer",
                  background: i === activeIdx ? "#4a9eff" : "#333",
                  color: i === activeIdx ? "#111" : "#ccc",
                  borderRadius: 3,
                }}
                title={ev.file_path ?? ev.bash_command ?? ""}
              >
                {ev.tool_name}
              </div>
            ))}
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
                <div style={{ display: "flex", gap: 12 }}>
                  <div style={{ flex: 1 }}>
                    <div style={labelStyle}>before</div>
                    <pre style={paneStyle}>{active.before_content ?? "(none)"}</pre>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={labelStyle}>after</div>
                    <pre style={paneStyle}>{active.after_content ?? "(none)"}</pre>
                  </div>
                </div>
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

const labelStyle: React.CSSProperties = {
  fontSize: 11,
  opacity: 0.6,
  marginBottom: 4,
  textTransform: "uppercase",
};
