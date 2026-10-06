// What of an agent's answers is shown, and what of it is new. Pure functions, so they can be
// tested without a browser.
import type { AnswerText, Turn } from './api'

/**
 * The texts of a request that are shown: all of them, or the summaries. What the user typed in
 * the middle of an answer starts a new stretch, so each message of the user, that of the request
 * and those typed during the answer, gets the last text written before the next one.
 */
export function shownTexts(turn: Turn, all: boolean): AnswerText[] {
  if (all) return turn.texts
  // ISO times in the same format compare as text.
  const boundaries = turn.interjections.filter((i) => !i.pending).map((i) => i.time).sort()
  const stretchOf = (text: AnswerText) => boundaries.filter((time) => time <= text.time).length
  return turn.texts.filter((text, index) => {
    const next = turn.texts[index + 1]
    return next === undefined || stretchOf(next) !== stretchOf(text)
  })
}

/** The shown texts written after `seen` (an ISO time, which compares as text), in the order written. */
export function unreadTexts(turns: Turn[], all: boolean, seen: string): AnswerText[] {
  return turns.flatMap((turn) => shownTexts(turn, all)).filter((text) => text.time > seen)
}
