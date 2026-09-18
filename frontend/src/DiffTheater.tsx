import { useMemo, useState } from "react";
import { diffWordsWithSpace } from "diff";
import "./DiffTheater.css";

interface Props {
  before: string | null;
  after: string | null;
  // Changing this remounts the animation -- the caller passes the active
  // event's tool_use_id so scrubbing to a different event replays the
  // morph from scratch instead of leaving stale animation state behind.
  eventKey: string;
}

// The single highest-leverage visual moment in Playhead, per the plan: not
// a static red/green diff table, but insertions/deletions animating in
// staggered by chunk so the whole edit reads as something that happened,
// not something you have to parse. diffWordsWithSpace (not diffChars) is
// used deliberately -- character-level diffing on real code produces noisy,
// meaningless single-letter fragments; word-level chunks are what a human
// actually perceives as "the part that changed."
export default function DiffTheater({ before, after, eventKey }: Props) {
  const [replayNonce, setReplayNonce] = useState(0);

  const parts = useMemo(
    () => diffWordsWithSpace(before ?? "", after ?? ""),
    [before, after],
  );

  return (
    <div>
      <div className="diff-theater-controls">
        <button onClick={() => setReplayNonce((n) => n + 1)}>Replay</button>
      </div>
      <div className="diff-theater" key={`${eventKey}-${replayNonce}`}>
        {parts.map((part, i) => (
          <span
            key={i}
            className={part.added ? "diff-added" : part.removed ? "diff-removed" : "diff-same"}
            style={part.added || part.removed ? { animationDelay: `${i * 35}ms` } : undefined}
          >
            {part.value}
          </span>
        ))}
      </div>
    </div>
  );
}
