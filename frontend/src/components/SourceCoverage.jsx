import { useMemo } from "react";

function findExcerpt(text, excerpt) {
  const idx = text.indexOf(excerpt);
  if (idx !== -1) return [idx, idx + excerpt.length];

  // Fallback: whitespace-insensitive match, in case the LLM normalized
  // spacing/newlines when quoting. Indices still refer to the original text.
  const trimmed = excerpt.trim();
  if (!trimmed) return null;
  const pattern = trimmed
    .replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
    .replace(/\s+/g, "\\s+");
  try {
    const match = new RegExp(pattern).exec(text);
    if (match) return [match.index, match.index + match[0].length];
  } catch {
    return null;
  }
  return null;
}

function computeSegments(text, scenes) {
  const ranges = [];
  for (const scene of scenes) {
    if (!scene.source_excerpt) continue;
    const range = findExcerpt(text, scene.source_excerpt);
    if (range) ranges.push(range);
  }
  ranges.sort((a, b) => a[0] - b[0]);

  const merged = [];
  for (const [start, end] of ranges) {
    const last = merged[merged.length - 1];
    if (last && start <= last[1]) {
      last[1] = Math.max(last[1], end);
    } else {
      merged.push([start, end]);
    }
  }

  const segments = [];
  let cursor = 0;
  for (const [start, end] of merged) {
    if (start > cursor) {
      segments.push({ text: text.slice(cursor, start), covered: false });
    }
    segments.push({ text: text.slice(start, end), covered: true });
    cursor = end;
  }
  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), covered: false });
  }
  return segments;
}

export default function SourceCoverage({ text, scenes }) {
  const segments = useMemo(() => computeSegments(text, scenes), [text, scenes]);

  const coveredChars = segments
    .filter((s) => s.covered)
    .reduce((sum, s) => sum + s.text.length, 0);
  const coveragePct = text.length ? Math.round((100 * coveredChars) / text.length) : 0;

  return (
    <div className="source-coverage">
      <p className="coverage-summary">
        ~{coveragePct}% of the text is reflected in a scene below. Highlighted text
        was used; plain text was skipped.
      </p>
      <div className="coverage-text">
        {segments.map((seg, i) => (
          <span key={i} className={seg.covered ? "covered" : "uncovered"}>
            {seg.text}
          </span>
        ))}
      </div>
    </div>
  );
}
