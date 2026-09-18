# Playhead

**Replay and audit trail for AI coding agents — scrubbed like a video timeline, not read like a log.**

## The problem

Teams adopting Claude Code, Cursor, and Copilot at scale have no good way to answer "what did the agent actually touch, and was any of it outside scope?" after the fact. Git diffs show the end state, not the sequence of tool calls, file reads, and shell commands that produced it.

## The signature UI — a video editor, not a dashboard

The whole app is built around a horizontal multi-track timeline with a draggable playhead, like Premiere or Ableton, instead of a table of log rows.

- Each **track** = one file touched during a session. Each **block** on the track = one Edit/Write/Bash event, colored by type.
- Dragging the playhead scrubs a **diff theater** pane that morphs the file text character-by-character between before/after states as you move — not a static red/green diff, an animated transition, so you watch the edit happen rather than read two blocks of text.
- A **radial blast-radius map** beside the timeline replaces the usual sidebar file tree: a small force-directed graph where a pulse of light radiates outward from whichever file is active at the current playhead position, showing what it touched next.
- Bash commands play back in a synced **terminal-replay strip** beneath the tracks (asciinema-style), scrubbing in lockstep with the playhead.
- Anomalies (agent touched a file with no relation to the stated task, or outside the declared working directory) show up as a **red spike on the timeline ruler itself** — like an audio waveform peak — so you spot the outlier visually before reading anything.

**Why this is unique:** the interaction model is borrowed from video/audio editing, not from analytics dashboards or log viewers. It also makes for a far better demo — a 20-second recording of dragging the playhead through a real session beats any screenshot of a table.

## Architecture

- **Ingestion:** a Claude Code hook fires on every Edit/Write/Bash tool call, posts a structured event `{session_id, ts, tool, file, before, after, cwd, cmd}` to an ingestion API. Support Cursor/Copilot later via the same event schema.
- **Backend:** FastAPI ingestion endpoint → Postgres (or Timescale if event volume gets large) storing raw events + a derived `sessions` table. A background worker computes the blast-radius graph and anomaly scores per session.
- **Frontend:** React + a custom canvas/WebGL timeline component. The force-directed blast-radius map uses `react-three-fiber` or `d3-force` rendered in WebGL.
- **Auth/multi-tenant:** GitHub OAuth login, org = team, sessions scoped per repo.

## Build order

1. **Event schema + ingestion API.** Define the JSON event shape, write the FastAPI endpoint, store raw events in Postgres. Validate with a fake session via `curl` before any UI exists.
2. **Real hook emitting real events.** Wire a Claude Code hook to POST real events during an actual coding session. Confirm the event stream captures everything needed (before/after content, cwd, timestamps) before visualizing it.
3. **Flat timeline, no styling.** One track per file, blocks placed by timestamp, a naive `<input type=range>` playhead. Proves the data model supports scrubbing.
4. **Diff theater with real morphing.** Compute a Myers diff between before/after, animate insertions/deletions over ~300ms keyed to playhead position. Highest-leverage visual moment in the product.
5. **Custom canvas timeline + terminal replay strip.** Replace the placeholder range input with the real multi-track canvas timeline; add the synced bash-replay strip underneath.
6. **Blast-radius radial map.** Force-directed file graph with pulse-on-active-file animation.
7. **Anomaly detection pass.** Start with a heuristic (files touched outside the PR's declared scope), surface as ruler spikes. Refine later.
8. **Multi-session / team view.** Only after the single-session experience is genuinely good.

## Status

Scaffold stage — step 1 in progress.
