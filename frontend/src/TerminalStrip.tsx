import "./TerminalStrip.css";
import type { PlayheadEvent } from "./api";

interface Props {
  events: PlayheadEvent[];
  playheadTs: number;
}

// Synced to the same playhead as the canvas timeline and the diff theater:
// as you scrub across a Bash event's [ts_start, ts_end] window, its output
// progressively reveals, asciinema-style, instead of dumping the whole
// command output the instant you touch its block.
export default function TerminalStrip({ events, playheadTs }: Props) {
  const bashEvents = events.filter((e) => e.tool_name === "Bash");

  let current: PlayheadEvent | null = null;
  for (const ev of bashEvents) {
    if (ev.ts_start <= playheadTs) current = ev;
    else break; // events arrive pre-ordered by ts_start from the API
  }

  if (!current) {
    return <div className="terminal-strip terminal-strip-empty">$ (no shell command reached yet)</div>;
  }

  const duration = Math.max(current.ts_end - current.ts_start, 0.001);
  const fraction = Math.min(Math.max((playheadTs - current.ts_start) / duration, 0), 1);
  const output = current.bash_output ?? "";
  const revealed = output.slice(0, Math.floor(output.length * fraction));
  const stillPlaying = fraction < 1;

  return (
    <div className="terminal-strip">
      <span className="terminal-strip-prompt">$ </span>
      {current.bash_command}
      {"\n"}
      {revealed}
      {stillPlaying && <span className="terminal-strip-cursor" />}
    </div>
  );
}
