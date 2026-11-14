/** Esc twice within this time opens the Rewind list of Claude Code (a list of earlier messages),
 * which looks like an interrupt that did not work: measured with Claude Code 2.1.325, 0.3 s apart
 * it opens, 0.9 s apart it does not. */
export const ESCAPE_REPEAT_GUARD_MILLISECONDS = 1000

/** Whether an Esc at `now` follows the last one that went to the agent (`previousAt`, null: none
 * yet) so closely that it is left out. */
export function isRepeatedEscape(previousAt: number | null, now: number): boolean {
  return previousAt !== null && now - previousAt < ESCAPE_REPEAT_GUARD_MILLISECONDS
}
