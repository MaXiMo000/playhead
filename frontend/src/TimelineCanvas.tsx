import { useEffect, useMemo, useRef } from "react";
import type { PlayheadEvent } from "./api";
import "./TimelineCanvas.css";

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

const TRACK_HEIGHT = 36;
const LABEL_WIDTH = 176;
const MIN_BLOCK_PX = 6;
const RULER_HEIGHT = 22;
const BLOCK_RADIUS = 5;

export const COLORS: Record<string, string> = {
  Edit: "#5b9dff",
  Write: "#a78bfa",
  Bash: "#f5a962",
};

const BG_TOP = "#12151c";
const BG_ALT = "#151922";
const GRID_LINE = "rgba(255,255,255,0.045)";
const RULER_BG = "#0e1015";

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

function dominantColor(track: Track): string {
  return COLORS[track.events[0].tool_name] ?? "#777";
}

function roundRectPath(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
}

// A real multi-track timeline on <canvas>, in the register of a video/audio
// editor -- tracks stacked vertically, events as blocks placed by real
// timestamp, a draggable playhead -- rather than a generic chart.
export default function TimelineCanvas({ events, playheadTs, onScrub }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);

  const tracks = useMemo(() => buildTracks(events), [events]);
  const minTs = events[0]?.ts_start ?? 0;
  const maxTs = events[events.length - 1]?.ts_end ?? minTs + 1;
  const span = Math.max(maxTs - minTs, 0.001);

  const height = RULER_HEIGHT + tracks.length * TRACK_HEIGHT + 14;

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
      ctx.textBaseline = "middle";

      const trackAreaWidth = cssWidth - LABEL_WIDTH;
      const tsToX = (ts: number) => LABEL_WIDTH + ((ts - minTs) / span) * trackAreaWidth;

      // Ruler band with faint vertical gridlines dropping through every track,
      // like a real timeline ruler rather than a bare strip.
      ctx.fillStyle = RULER_BG;
      ctx.fillRect(0, 0, cssWidth, RULER_HEIGHT);
      ctx.strokeStyle = GRID_LINE;
      ctx.lineWidth = 1;
      for (const ev of events) {
        const gx = Math.round(tsToX(ev.ts_start)) + 0.5;
        ctx.beginPath();
        ctx.moveTo(gx, RULER_HEIGHT);
        ctx.lineTo(gx, height);
        ctx.stroke();
      }
      // Tick marks + anomaly spikes on the ruler itself
      for (const ev of events) {
        const x = tsToX(ev.ts_start);
        if (ev.is_anomalous) {
          ctx.fillStyle = "#f87171";
          ctx.shadowColor = "rgba(248,113,113,0.7)";
          ctx.shadowBlur = 6;
          ctx.beginPath();
          ctx.moveTo(x - 4, RULER_HEIGHT - 2);
          ctx.lineTo(x + 4, RULER_HEIGHT - 2);
          ctx.lineTo(x, RULER_HEIGHT - 12);
          ctx.closePath();
          ctx.fill();
          ctx.shadowBlur = 0;
        } else {
          ctx.fillStyle = "rgba(255,255,255,0.18)";
          ctx.fillRect(x - 0.5, RULER_HEIGHT - 6, 1, 6);
        }
      }

      tracks.forEach((track, i) => {
        const y = RULER_HEIGHT + i * TRACK_HEIGHT;
        const dotColor = dominantColor(track);

        ctx.fillStyle = i % 2 === 0 ? BG_TOP : BG_ALT;
        ctx.fillRect(0, y, cssWidth, TRACK_HEIGHT);
        ctx.strokeStyle = GRID_LINE;
        ctx.beginPath();
        ctx.moveTo(0, y + TRACK_HEIGHT);
        ctx.lineTo(cssWidth, y + TRACK_HEIGHT);
        ctx.stroke();

        // File-type dot + label chip
        ctx.beginPath();
        ctx.arc(14, y + TRACK_HEIGHT / 2, 3, 0, Math.PI * 2);
        ctx.fillStyle = dotColor;
        ctx.fill();

        ctx.fillStyle = "#c7cbd6";
        ctx.font = "500 11.5px 'JetBrains Mono', monospace";
        ctx.fillText(track.label, 26, y + TRACK_HEIGHT / 2 + 1, LABEL_WIDTH - 36);

        for (const ev of track.events) {
          const x0 = tsToX(ev.ts_start);
          const x1 = Math.max(tsToX(ev.ts_end), x0 + MIN_BLOCK_PX);
          const isActive = playheadTs >= ev.ts_start && playheadTs <= ev.ts_end;
          const blockY = y + 6;
          const blockH = TRACK_HEIGHT - 12;
          const color = COLORS[ev.tool_name] ?? "#777";

          if (isActive) {
            ctx.shadowColor = color;
            ctx.shadowBlur = 14;
          }

          const grad = ctx.createLinearGradient(0, blockY, 0, blockY + blockH);
          grad.addColorStop(0, color);
          grad.addColorStop(1, shade(color, -18));
          ctx.fillStyle = grad;
          ctx.globalAlpha = isActive ? 1 : 0.72;
          roundRectPath(ctx, x0, blockY, x1 - x0, blockH, BLOCK_RADIUS);
          ctx.fill();
          ctx.globalAlpha = 1;
          ctx.shadowBlur = 0;

          if (ev.tool_reported_success === false) {
            ctx.strokeStyle = "#f87171";
            ctx.lineWidth = 2;
            ctx.setLineDash([]);
            roundRectPath(ctx, x0, blockY, x1 - x0, blockH, BLOCK_RADIUS);
            ctx.stroke();
          }
          if (ev.is_anomalous) {
            ctx.strokeStyle = "#fb923c";
            ctx.lineWidth = 1.5;
            ctx.setLineDash([3, 2]);
            roundRectPath(ctx, x0, blockY, x1 - x0, blockH, BLOCK_RADIUS);
            ctx.stroke();
            ctx.setLineDash([]);
          }
        }
      });

      // Playhead: soft vertical glow beam + a rounded handle
      const px = tsToX(playheadTs);
      const beamGrad = ctx.createLinearGradient(px - 10, 0, px + 10, 0);
      beamGrad.addColorStop(0, "rgba(255,255,255,0)");
      beamGrad.addColorStop(0.5, "rgba(255,255,255,0.06)");
      beamGrad.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = beamGrad;
      ctx.fillRect(px - 10, 0, 20, height);

      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1.5;
      ctx.shadowColor = "rgba(255,255,255,0.5)";
      ctx.shadowBlur = 4;
      ctx.beginPath();
      ctx.moveTo(px, 0);
      ctx.lineTo(px, height);
      ctx.stroke();
      ctx.shadowBlur = 0;

      ctx.fillStyle = "#ffffff";
      roundRectPath(ctx, px - 6, 0, 12, 11, 3);
      ctx.fill();
    };

    draw();
    const observer = new ResizeObserver(draw);
    observer.observe(container);
    return () => observer.disconnect();
  }, [tracks, events, playheadTs, minTs, span, height]);

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
    <div ref={containerRef} className="timeline-canvas-container">
      <canvas
        ref={canvasRef}
        className="timeline-canvas"
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

function shade(hex: string, percent: number): string {
  const num = parseInt(hex.slice(1), 16);
  const amt = Math.round(2.55 * percent);
  const r = Math.min(255, Math.max(0, (num >> 16) + amt));
  const g = Math.min(255, Math.max(0, ((num >> 8) & 0x00ff) + amt));
  const b = Math.min(255, Math.max(0, (num & 0x0000ff) + amt));
  return `#${(0x1000000 + r * 0x10000 + g * 0x100 + b).toString(16).slice(1)}`;
}
