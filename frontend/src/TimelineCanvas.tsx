import { useEffect, useMemo, useRef } from "react";
import type { PlayheadEvent } from "./api";

interface Props {
  events: PlayheadEvent[];
  playheadTs: number;
  onScrub: (ts: number) => void;
}

interface Track {
  key: string;
  label: string;
  events: PlayheadEvent[];
}

const TRACK_HEIGHT = 30;
const LABEL_WIDTH = 170;
const MIN_BLOCK_PX = 5;
const COLORS: Record<string, string> = {
  Edit: "#4a9eff",
  Write: "#b388ff",
  Bash: "#ffb84a",
};

function trackKeyFor(ev: PlayheadEvent): string {
  if (ev.tool_name === "Bash") return "\0shell"; // sorts last, deliberately
  return ev.file_path ?? "\0other";
}

function buildTracks(events: PlayheadEvent[]): Track[] {
  const byKey = new Map<string, PlayheadEvent[]>();
  for (const ev of events) {
    const key = trackKeyFor(ev);
    if (!byKey.has(key)) byKey.set(key, []);
    byKey.get(key)!.push(ev);
  }
  const tracks = [...byKey.entries()].map(([key, evs]) => ({
    key,
    label: key === "\0shell" ? "shell" : key === "\0other" ? "other" : shortenPath(key),
    events: evs,
  }));
  // Files ordered by first appearance, shell track always last -- a session
  // usually reads top-to-bottom in the order files were first touched.
  tracks.sort((a, b) => {
    if (a.key === "\0shell") return 1;
    if (b.key === "\0shell") return -1;
    return a.events[0].ts_start - b.events[0].ts_start;
  });
  return tracks;
}

function shortenPath(path: string): string {
  const parts = path.split(/[/\\]/);
  return parts.length > 2 ? `.../${parts.slice(-2).join("/")}` : path;
}

// A real multi-track timeline on <canvas>, in the register of a video/audio
// editor -- tracks stacked vertically, events as blocks placed by real
// timestamp, a draggable playhead -- rather than a generic chart. This
// replaces the placeholder <input type=range> and flat block row from
// step 8a now that the underlying data model (sessions -> ordered events
// -> a scrubbable position) is already proven to work.
export default function TimelineCanvas({ events, playheadTs, onScrub }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);

  const tracks = useMemo(() => buildTracks(events), [events]);
  const minTs = events[0]?.ts_start ?? 0;
  const maxTs = events[events.length - 1]?.ts_end ?? minTs + 1;
  const span = Math.max(maxTs - minTs, 0.001);

  const height = tracks.length * TRACK_HEIGHT + 20;

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const draw = () => {
      const cssWidth = container.clientWidth;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = cssWidth * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${cssWidth}px`;
      canvas.style.height = `${height}px`;

      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, cssWidth, height);

      const trackAreaWidth = cssWidth - LABEL_WIDTH;
      const tsToX = (ts: number) => LABEL_WIDTH + ((ts - minTs) / span) * trackAreaWidth;

      tracks.forEach((track, i) => {
        const y = i * TRACK_HEIGHT + 10;

        ctx.fillStyle = i % 2 === 0 ? "#1c1c1c" : "#181818";
        ctx.fillRect(0, y, cssWidth, TRACK_HEIGHT);

        ctx.fillStyle = "#999";
        ctx.font = "11px ui-monospace, monospace";
        ctx.textBaseline = "middle";
        ctx.fillText(track.label, 8, y + TRACK_HEIGHT / 2, LABEL_WIDTH - 16);

        for (const ev of track.events) {
          const x0 = tsToX(ev.ts_start);
          const x1 = Math.max(tsToX(ev.ts_end), x0 + MIN_BLOCK_PX);
          const isActive = playheadTs >= ev.ts_start && playheadTs <= ev.ts_end;

          ctx.fillStyle = COLORS[ev.tool_name] ?? "#777";
          ctx.globalAlpha = isActive ? 1 : 0.65;
          ctx.fillRect(x0, y + 4, x1 - x0, TRACK_HEIGHT - 8);
          ctx.globalAlpha = 1;

          if (ev.tool_reported_success === false) {
            ctx.strokeStyle = "#ff4444";
            ctx.lineWidth = 2;
            ctx.strokeRect(x0, y + 4, x1 - x0, TRACK_HEIGHT - 8);
          }
        }
      });

      // Playhead
      const px = tsToX(playheadTs);
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(px, 0);
      ctx.lineTo(px, height);
      ctx.stroke();
      ctx.fillStyle = "#fff";
      ctx.beginPath();
      ctx.moveTo(px - 5, 0);
      ctx.lineTo(px + 5, 0);
      ctx.lineTo(px, 8);
      ctx.closePath();
      ctx.fill();
    };

    draw();
    const observer = new ResizeObserver(draw);
    observer.observe(container);
    return () => observer.disconnect();
  }, [tracks, playheadTs, minTs, span, height]);

  const xToTs = (clientX: number): number => {
    const canvas = canvasRef.current;
    if (!canvas) return playheadTs;
    const rect = canvas.getBoundingClientRect();
    const x = clientX - rect.left;
    const trackAreaWidth = rect.width - LABEL_WIDTH;
    const frac = (x - LABEL_WIDTH) / trackAreaWidth;
    return minTs + Math.min(Math.max(frac, 0), 1) * span;
  };

  return (
    <div ref={containerRef} style={{ width: "100%" }}>
      <canvas
        ref={canvasRef}
        style={{ display: "block", cursor: "pointer", borderRadius: 4 }}
        onMouseDown={(e) => {
          draggingRef.current = true;
          onScrub(xToTs(e.clientX));
        }}
        onMouseMove={(e) => {
          if (draggingRef.current) onScrub(xToTs(e.clientX));
        }}
        onMouseUp={() => {
          draggingRef.current = false;
        }}
        onMouseLeave={() => {
          draggingRef.current = false;
        }}
      />
    </div>
  );
}
