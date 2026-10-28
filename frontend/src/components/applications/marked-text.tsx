import { Fragment } from "react";
import { cn } from "@/lib/utils";

// The assistant writes anything it added for one ad — a skill the CV does not state —
// inside [[double brackets]]. Backend PDF renders those red; this is the same rule on
// screen, so what he reads on screen and in the PDF always matches.
const SUGGESTION = /\[\[([^\[\]\n]{1,80})\]\]/g;

const LEGEND = "RED ITEMS ARE SUGGESTIONS";
const BLOCK_HEADING = "SUGGESTED FOR THIS AD";

/** The additions this document carries, in the order it lists them. */
export function suggestedItems(text: string): string[] {
  return [...(text ?? "").matchAll(SUGGESTION)].map((m) => m[1].trim()).filter(Boolean);
}

function splitSuggestions(line: string) {
  const parts: Array<{ text: string; added: boolean }> = [];
  let last = 0;
  for (const m of line.matchAll(SUGGESTION)) {
    const start = m.index ?? 0;
    if (start > last) parts.push({ text: line.slice(last, start), added: false });
    parts.push({ text: m[1], added: true });
    last = start + m[0].length;
  }
  if (last < line.length) parts.push({ text: line.slice(last), added: false });
  return parts;
}

/** Document text with every assistant-added line drawn red and underlined. */
export function MarkedText({ text, className }: { text: string; className?: string }) {
  const lines = (text ?? "").split("\n");
  return (
    <pre className={cn("whitespace-pre-wrap break-words font-mono text-xs leading-relaxed", className)}>
      {lines.map((line, i) => {
        const trimmed = line.trim();
        const tone = trimmed.startsWith(LEGEND)
          ? "text-red-700 italic dark:text-red-400"
          : trimmed.startsWith(BLOCK_HEADING)
            ? "text-red-700 font-semibold dark:text-red-400"
            : "";
        return (
          <Fragment key={i}>
            <span className={tone}>
              {splitSuggestions(line).map((part, j) =>
                part.added ? (
                  <span
                    key={j}
                    className="rounded-sm bg-red-500/10 px-0.5 font-semibold text-red-700 underline decoration-red-600/70 underline-offset-2 dark:text-red-400"
                  >
                    {part.text}
                  </span>
                ) : (
                  part.text
                )
              )}
            </span>
            {"\n"}
          </Fragment>
        );
      })}
    </pre>
  );
}
