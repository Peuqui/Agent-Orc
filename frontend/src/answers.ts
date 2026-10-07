// What of an agent's answers is shown, and what of it is new. Pure functions, so they can be
// tested without a browser.
import type { AnswerText, SpokenRequest, Turn } from './api'

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

/** New to the reader: written after the time seen, and not read aloud since. */
export function isUnread(text: AnswerText, seen: string, read: ReadonlySet<string>): boolean {
  return text.time > seen && !read.has(text.id)
}

/** The shown texts written after `seen` (an ISO time, which compares as text), in the order written. */
export function unreadTexts(turns: Turn[], all: boolean, seen: string): AnswerText[] {
  return turns.flatMap((turn) => shownTexts(turn, all)).filter((text) => text.time > seen)
}

// A picture attached in Agent-Orc is stored in the agent's folder and its path goes into the
// message ("@path", as Claude Code reads files); the answers show it as a picture instead.
const UPLOAD_MENTION = /@\.agent-orc\/uploads\/([A-Za-z0-9._-]+\.(?:png|jpe?g|gif|webp))/gi

/** The text of a message without the pictures it names, and the file names of those pictures. */
export function uploadMentions(text: string): { text: string; files: string[] } {
  const files = [...text.matchAll(UPLOAD_MENTION)].map((match) => match[1])
  return { text: text.replace(UPLOAD_MENTION, '').replace(/[ \t]*\n[ \t]*/g, '\n').replace(/[ \t]+/g, ' ').trim(), files }
}

/** The spoken request a turn is: the latest one sent before it with the same text, if any. */
export function spokenAs(turn: Turn, spoken: SpokenRequest[]): SpokenRequest | undefined {
  const asked = Date.parse(turn.time)
  return spoken.findLast((entry) => entry.request === turn.prompt && Date.parse(entry.time) <= asked)
}
