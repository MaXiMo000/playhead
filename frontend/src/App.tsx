import { useEffect, useMemo, useState } from "react";
import { fetchSessionEvents, fetchSessions, type PlayheadEvent, type SessionSummary } from "./api";
import DiffTheater from "./DiffTheater";
import TimelineCanvas, { COLORS } from "./TimelineCanvas";
import TerminalStrip from "./TerminalStrip";
import BlastRadiusMap from "./BlastRadiusMap";
import SessionList from "./SessionList";
import "./App.css";

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
    <div className="app-root">
      <header className="app-topbar">
        <div className="app-logo">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M6 4L20 12L6 20V4Z" fill="white" />
          </svg>
        </div>
        <h1 className="app-title">Playhead</h1>
        <span className="app-subtitle">Replay and audit trail for AI coding agents</span>
      </header>

      {error && <div className="app-error">{error}</div>}

      <div className="app-body">
        <aside className="app-sidebar">
          <div className="section-heading">
            <span className="eyebrow">Sessions</span>
          </div>
          <SessionList sessions={sessions} selectedSession={selectedSession} onSelect={setSelectedSession} />
        </aside>

        <main className="app-main">
          {events.length === 0 ? (
            <div className="app-empty-state">
              <span>Select a session to start scrubbing.</span>
            </div>
          ) : (
            <>
              <div className="card section-card workspace-timeline">
                <div className="section-heading">
                  <span className="eyebrow">Timeline</span>
                </div>
                <TimelineCanvas events={events} playheadTs={playheadTs} onScrub={setPlayheadTs} />
              </div>

              <div className="workspace-grid">
                <div>
                  {active && (
                    <div className="card section-card">
                      <div className="detail-header">
                        <span
                          className="detail-icon"
                          style={{ background: COLORS[active.tool_name] ?? "#8b93a7" }}
                        />
                        <span className="detail-path">
                          {active.tool_name} — {active.file_path ?? active.bash_command}
                        </span>
                        {active.tool_reported_success === true && (
                          <span className="pill pill-success">success</span>
                        )}
                        {active.tool_reported_success === false && (
                          <span className="pill pill-fail">failed</span>
                        )}
                        {active.tool_reported_success === null && (
                          <span className="pill pill-unverified">unverified</span>
                        )}
                        {active.is_anomalous && (
                          <span className="pill pill-anomaly">⚠ outside working directory</span>
                        )}
                      </div>
                      {active.tool_name === "Bash" ? (
                        <pre className="bash-output-pane">{active.bash_output ?? "(no output)"}</pre>
                      ) : (
                        <DiffTheater
                          before={active.before_content}
                          after={active.after_content}
                          eventKey={active.tool_use_id}
                        />
                      )}
                    </div>
                  )}
                </div>

                <div className="workspace-secondary">
                  <TerminalStrip events={events} playheadTs={playheadTs} />
                  <BlastRadiusMap events={events} playheadTs={playheadTs} />
                </div>
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
