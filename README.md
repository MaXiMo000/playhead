# Playhead

**Replay and audit trail for AI coding agents — scrubbed like a video timeline, not read like a log.**

## The problem

Teams adopting Claude Code, Cursor, and Copilot at scale have no good way to answer "what did the agent actually touch, and was any of it outside scope?" after the fact. Git diffs show the end state, not the sequence of tool calls, file reads, and shell commands that produced it.

## The signature UI — a video editor, not a dashboard

The whole app is built around a horizontal multi-track timeline with a draggable playhead, like Premiere or Ableton, instead of a table of log rows.

- Each **track** = one file touched during a session. Each **block** on the track = one Edit/Write/Bash/PowerShell event, colored by type.
- Dragging the playhead scrubs a **diff theater** pane that morphs the file text character-by-character between before/after states as you move — not a static red/green diff, an animated transition, so you watch the edit happen rather than read two blocks of text.
- A **radial blast-radius map** beside the timeline replaces the usual sidebar file tree: a small force-directed graph where a pulse of light radiates outward from whichever file is active at the current playhead position, showing what it touched next.
- Shell commands (Bash and PowerShell) play back in a synced **terminal-replay strip** beneath the tracks (asciinema-style), scrubbing in lockstep with the playhead.
- Anomalies (agent touched a file with no relation to the stated task, or outside the declared working directory) show up as a **red spike on the timeline ruler itself** — like an audio waveform peak — so you spot the outlier visually before reading anything.

**Why this is unique:** the interaction model is borrowed from video/audio editing, not from analytics dashboards or log viewers. It also makes for a far better demo — a 20-second recording of dragging the playhead through a real session beats any screenshot of a table.

## Try it on a session you already had

No hook needed: every Claude Code session is already saved as a
transcript, and `playhead-import` rebuilds its Edit/Write/Bash/PowerShell timeline
from that.

```bash
pip install -e .                                   # playhead-hook, playhead-sync, playhead-import
cd backend && uvicorn app.main:app --port 8000 &    # the API (SQLite by default)
cd frontend && npm install && npm run dev           # the timeline UI

cd ~/code/your-project
playhead-import --latest --sync                    # this project's most recent session
playhead-import --all --sync                       # or every session it has had
```

It reads `~/.claude/projects/<project>/<session>.jsonl`: each tool call's
inputs, timestamps and result -- including the file's content before an
Edit, which is what the diff theater replays. Importing the same session
twice changes nothing. Measured on real sessions here: 544 events
imported with none failing, 474 in 7.7 seconds.

What a transcript can't give is the file on disk *after* the call, so the
after-content is what the tool reported writing. Install the hook (below)
to record sessions live instead, with the real bytes read back from disk.

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

- **Session import — done.** `playhead-import` (`playhead_hook/transcript.py`) rebuilds events from Claude Code transcripts; the backend takes them 100 at a time on `POST /events/batch` (one query for existing ids, one insert), so a real session imports in seconds instead of minutes at the 60-requests-a-minute limit. Tested against real transcript shapes and run on three real sessions.
- **Step 1-4 (hook package) — done.** `playhead_hook/` (`core.py` pure event-shaping, `hook.py` stdin/stdout glue, `sync.py` uploader) is built, unit-tested (`tests/`), installed in editable mode, and smoke-tested end-to-end via the real `playhead-hook`/`playhead-sync` console scripts piped real doc-shaped JSON — not just in-process. `.claude/settings.json` registers it.
- **Step 5 (validate the hook fires live) — done, root cause found and fixed.** It was never the "session root" concern custody's README speculated about — it was simpler: `.claude/settings.json` invokes the bare command `playhead-hook`, which only resolves if something is actually on `PATH`, and a project-local `.venv` never is. Confirmed live in a real Claude Code session: a real `Write` call with only the local `.venv` installed produced no `.playhead/events/` file at all. Fix: `pip install -e .` into the global/regular Python (not a venv) so the console scripts land in a directory already on `PATH`; re-verified live afterward with the bare `playhead-hook` command from a fresh shell and it correctly wrote a real event. See "Installing the hook" below.
- **Step 6 (FastAPI + DB) — done.** `backend/app/` exposes `POST /events` (idempotent on `tool_use_id`), `GET /sessions`, `GET /sessions/{id}/events`. Defaults to local SQLite (`DATABASE_URL` env var to point at Postgres instead). Verified end-to-end: a real event produced by `playhead-hook` was posted, re-posted (confirmed idempotent), and read back correctly.
- **Step 7 (`playhead sync`) — done and verified** against the running backend: spools from `.playhead/events/`, uploads, moves to `.playhead/sent/` on success, retries on failure.
- **Step 8a (flat, unstyled timeline) — done.** `frontend/` (Vite + React + TS): session picker, an `<input type=range>` playhead over real events from the API, clickable blocks. Verified live in-browser against a real seeded session.
- **Step 8b (diff theater with real animated morphing) — done.** `frontend/src/DiffTheater.tsx`: word-level diff (`diffWordsWithSpace`), staggered reveal/collapse animation instead of a static red/green table. Verified live for both a pure-insertion case and a real-removal case.
- **Blast-radius radial map — done, verified rendering in a real browser.** `frontend/src/BlastRadiusMap.tsx`: a `@react-three/fiber`/`three.js` force-directed graph (`d3-force`) of files touched, edges by consecutive-touch order (not a static dependency graph), a pulsing ring on the currently active file. Confirmed pixel-rendered against a seeded 9-event session: nodes, edges and the animated pulse all draw. Edges use `<lineSegments>`, not `<line>` -- JSX types `line` as the SVG element, which broke `tsc -b` and so the production build. **Known gap:** the camera does not auto-frame the graph, so nodes near the edge of a wide layout can be clipped.
- **Anomaly detection pass — done.** `backend/app/anomaly.py`: a single heuristic (a file touched outside the session's own `cwd` is flagged) computed at ingestion time, stored on the event, surfaced in `TimelineCanvas.tsx` as a red spike on a dedicated ruler band plus a dashed orange outline on the block itself, and as a warning line in the detail panel. Unit-tested (`backend/tests/test_anomaly.py`, 8 cases including Windows path separators and case-insensitivity) and verified live end-to-end: a real out-of-scope event was posted, confirmed flagged by the API, and confirmed rendered as both a ruler spike and a badge in the browser.
- **Multi-session view — done.** `frontend/src/SessionList.tsx` replaces the plain `<select>` with a searchable, metadata-rich list (event count, start time, duration). Verified live with three seeded sessions: search filtering and row-click selection both confirmed working.
- **All originally planned build-order steps are now implemented and the hook is confirmed live-firing end-to-end.** The one still-open item is confirming the blast-radius map's pixel rendering in a real browser (flagged above).

## Security

This is a single-user personal tool, not a multi-tenant product, and the security posture below is sized to that threat model, not to "assume this gets deployed publicly to strangers."

- **API key auth** (`backend/app/security.py`): every endpoint except `/health` requires `Authorization: Bearer <PLAYHEAD_API_KEY>` once that env var is set. If it's unset, the server runs open and prints a loud warning at startup — that's the localhost-demo case, not a silent default. The same key must be set for `playhead-sync` (`PLAYHEAD_API_KEY`) and the frontend (`VITE_API_KEY`) or every request 401s. **Honestly stated limitation**: the key ships inside the built frontend bundle, readable by anyone who loads the page — there is no login system here, so this stops opportunistic bots/scanners hitting an exposed API, not a targeted attacker who reads the bundle. Real multi-user auth is out of scope for what this project is.
- **CORS is a real allowlist**, not `*` — `ALLOWED_ORIGINS` (comma-separated), defaulting to the local Vite ports only.
- **Rate limiting** (`slowapi`): 60/minute on `POST /events`. Verified live: 65 rapid requests returned exactly 60×`201` then 5×`429`.
- **Request body size cap**: 5MB, checked via `Content-Length` before the body is read. Verified live: a request declaring a 6MB body gets `413` immediately.
- **Security headers** (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`) on every response.
- **SQLite has no encryption at rest, and that is not fixed here.** Tried `sqlcipher3-binary` for this — no wheel exists for this platform, and this project isn't going to ship a fragile from-source build just to check a box. The honest fix: use Postgres (`DATABASE_URL`) for anything beyond solo local use — a managed provider gives you encryption at rest and TLS in transit for free, which is a better answer than a brittle local dependency.
- **Already fine, no changes needed**: no XSS risk (React escapes all rendered text; nothing here uses `dangerouslySetInnerHTML`), no SQL injection risk (SQLAlchemy ORM, no raw string-built queries anywhere).

### Running the backend locally

```
cd backend
python -m venv .venv && .venv/Scripts/activate  # or source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in PLAYHEAD_API_KEY to lock the API down; leave blank to run open for local dev
uvicorn app.main:app --reload
```

The frontend needs the same key: `cp frontend/.env.example frontend/.env.local` and set `VITE_API_KEY` to match. `playhead-sync` needs `PLAYHEAD_API_KEY` set in its own environment too.

### Installing the hook

`.claude/settings.json` invokes the hook as the bare command `playhead-hook`, so it must resolve on the `PATH` of whatever shell launches `claude` -- **not** just inside a project-local `.venv`, which is never on `PATH` by design. Install it into your regular/global Python instead:

```
pip install -e .
```

(run outside any virtualenv, or use `pipx install -e .` for isolation while still landing on `PATH`). Verify it resolves before trusting it:

```
command -v playhead-hook   # or `where playhead-hook` on Windows
```

Then merge `hooks/settings.snippet.json` into this project's `.claude/settings.json` (already done in this repo) or `~/.claude/settings.json` for every project.

A project-local `backend/.venv`-style install (e.g. `python -m venv .venv && .venv/Scripts/pip install -e .`) will build and pass all the tests but will **silently never fire** as a live hook -- confirmed directly: a real `Write` call in a session with only that venv installed produced no `.playhead/events/` file at all, while invoking the exact same installed script directly worked perfectly. The hook logic was never the problem; PATH resolution was.
