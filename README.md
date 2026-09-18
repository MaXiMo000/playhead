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

- **Step 1-4 (hook package) — done.** `playhead_hook/` (`core.py` pure event-shaping, `hook.py` stdin/stdout glue, `sync.py` uploader) is built, unit-tested (`tests/`), installed in editable mode, and smoke-tested end-to-end via the real `playhead-hook`/`playhead-sync` console scripts piped real doc-shaped JSON — not just in-process. `.claude/settings.json` registers it.
- **Step 5 (validate the hook actually fires in a live session) — not yet done, requires a human at the keyboard.** custody's own README documents a confirmed, unresolved finding: a `.claude/settings.json` in a directory a session merely `cd`s into mid-session never fires the hook — Claude Code reads project hooks from the session's root at launch. **Before trusting this pipeline for real**, start a fresh `claude` process with this repo (`playhead/`) as its own root, make one real edit, and confirm a file appears in `.playhead/events/`. See `hooks/settings.snippet.json` if wiring this into another project instead.
- **Step 6 (FastAPI + DB) — done.** `backend/app/` exposes `POST /events` (idempotent on `tool_use_id`), `GET /sessions`, `GET /sessions/{id}/events`. Defaults to local SQLite (`DATABASE_URL` env var to point at Postgres instead). Verified end-to-end: a real event produced by `playhead-hook` was posted, re-posted (confirmed idempotent), and read back correctly.
- **Step 7 (`playhead sync`) — done and verified** against the running backend: spools from `.playhead/events/`, uploads, moves to `.playhead/sent/` on success, retries on failure.
- **Step 8a (flat, unstyled timeline) — done.** `frontend/` (Vite + React + TS): session picker, an `<input type=range>` playhead over real events from the API, clickable blocks. Verified live in-browser against a real seeded session.
- **Step 8b (diff theater with real animated morphing) — done.** `frontend/src/DiffTheater.tsx`: word-level diff (`diffWordsWithSpace`), staggered reveal/collapse animation instead of a static red/green table. Verified live for both a pure-insertion case and a real-removal case.
- **Blast-radius radial map — built, correctness verified, full visual verification pending.** `frontend/src/BlastRadiusMap.tsx`: a `@react-three/fiber`/`three.js` force-directed graph (`d3-force`) of files touched, edges by consecutive-touch order (not a static dependency graph), a pulsing ring on the currently active file. Verified correct in-browser: TypeScript compiles clean, the graph/link computation over real seeded events produces the right nodes and edges, and a real WebGL context initializes. **Not yet confirmed pixel-rendered**: `@react-three/fiber`'s `<Canvas>` sizes itself via `ResizeObserver` (through `react-use-measure`), and this repo's automated preview pane's embedded WebKit view does not fire `ResizeObserver` callbacks at all (confirmed directly, independent of this component) — so the canvas never leaves its 300x150 fallback size in that one tool. This is a property of that specific preview embedding, not of real browsers, which support `ResizeObserver` universally — **please open `npm run dev` in an actual browser once and confirm the graph renders and the pulse animates** before relying on this component further.
- **Anomaly detection pass — done.** `backend/app/anomaly.py`: a single heuristic (a file touched outside the session's own `cwd` is flagged) computed at ingestion time, stored on the event, surfaced in `TimelineCanvas.tsx` as a red spike on a dedicated ruler band plus a dashed orange outline on the block itself, and as a warning line in the detail panel. Unit-tested (`backend/tests/test_anomaly.py`, 8 cases including Windows path separators and case-insensitivity) and verified live end-to-end: a real out-of-scope event was posted, confirmed flagged by the API, and confirmed rendered as both a ruler spike and a badge in the browser.
- **Multi-session view — done.** `frontend/src/SessionList.tsx` replaces the plain `<select>` with a searchable, metadata-rich list (event count, start time, duration). Verified live with three seeded sessions: search filtering and row-click selection both confirmed working.
- **All originally planned build-order steps are now implemented.** The one still-open item is the manual, human-only check flagged above (step 5: does the hook actually fire in a real top-level session) and confirming the blast-radius map's pixel rendering in a real browser.

### Running the backend locally

```
cd backend
python -m venv .venv && .venv/Scripts/activate  # or source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Installing the hook

```
pip install -e .
```
then merge `hooks/settings.snippet.json` into this project's `.claude/settings.json` (already done in this repo) or `~/.claude/settings.json` for every project.
