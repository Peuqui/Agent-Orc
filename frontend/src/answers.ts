// What of an agent's answers is shown, and what of it is new. Pure functions, so they can be
// tested without a browser.
import type { AnswerText, Turn } from './api'

/** The texts of a request that are shown: all of them, or the last one (its summary). */
export function shownTexts(turn: Turn, all: boolean): AnswerText[] {
  return all ? turn.texts : turn.texts.slice(-1)
}

/** The shown texts written after `seen` (an ISO time, which compares as text), in the order written. */
export function unreadTexts(turns: Turn[], all: boolean, seen: string): AnswerText[] {
  return turns.flatMap((turn) => shownTexts(turn, all)).filter((text) => text.time > seen)
}
