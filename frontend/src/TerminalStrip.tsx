import "./TerminalStrip.css";
import { isShell, type PlayheadEvent } from "./api";

interface Props {
  events: PlayheadEvent[];
  playheadTs: number;
}

// Synced to the same playhead as the canvas timeline and the diff theater:
// as you scrub across a Bash event's [ts_start, ts_end] window, its output
// progressively reveals, asciinema-style, instead of dumping the whole
// command output the instant you touch its block.
export default function TerminalStrip({ events, playheadTs }: Props) {
  const bashEvents = events.filter(isShell);

  let current: PlayheadEvent | null = null;
  for (const ev of bashEvents) {
    if (ev.ts_start <= playheadTs) current = ev;
    else break; // events arrive pre-ordered by ts_start from the API
  }

  const duration = current ? Math.max(current.ts_end - current.ts_start, 0.001) : 1;
  const fraction = current ? Math.min(Math.max((playheadTs - current.ts_start) / duration, 0), 1) : 0;
  const output = current?.bash_output ?? "";
  const revealed = output.slice(0, Math.floor(output.length * fraction));
  const stillPlaying = fraction < 1;

  return (
    <div className="terminal-window">
      <div className="terminal-titlebar">
        <span className="terminal-dot terminal-dot-red" />
        <span className="terminal-dot terminal-dot-yellow" />
        <span className="terminal-dot terminal-dot-green" />
        <span className="terminal-titlebar-label">shell</span>
      </div>
      <div className="terminal-body">
        {current ? (
          <>
            <span className="terminal-prompt">➜ </span>
            {current.bash_command}
            {"\n"}
            {revealed}
            {stillPlaying && <span className="terminal-cursor" />}
          </>
        ) : (
          <span className="terminal-empty">$ waiting for a shell command...</span>
        )}
      </div>
    </div>
  );
}
