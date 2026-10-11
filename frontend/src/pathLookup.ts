// Which of the paths a text names exist in a folder, and where: asked of the server once and kept
// for a while, whichever view asks (the terminal's links, the answers', the changes' open
// buttons), so one path is looked up once, not once per view and hover.
import type { ExistingPath } from './api'

type Ask = (base: string, candidates: string[]) => Promise<Record<string, ExistingPath>>

// How long an answer is kept. A path that exists seldom stops existing; one that does not may
// come into being any moment (the agent names a file before it has written it), so that is asked
// for again soon.
export const FOUND_TTL_MS = 5 * 60_000
export const MISSING_TTL_MS = 5_000
// So a long session does not collect them without end.
const MAX_KEPT = 2000

export function createPathLookup(
  ask: Ask,
  now: () => number = Date.now,
  ttl: { found: number; missing: number } = { found: FOUND_TTL_MS, missing: MISSING_TTL_MS },
) {
  /** What the server said per folder and path (null: it does not exist), and until when. */
  const kept = new Map<string, { found: ExistingPath | null; until: number }>()
  /** The request a path is being asked in. */
  const asking = new Map<string, Promise<void>>()
  const keyOf = (base: string, candidate: string): string => `${base}\n${candidate}`

  function isKept(key: string): boolean {
    const entry = kept.get(key)
    return entry !== undefined && entry.until > now()
  }

  /** Of the candidates, those that exist in `base`, as the server answers (absent: missing). */
  return async function lookUp(base: string, candidates: string[]): Promise<Record<string, ExistingPath>> {
    const wanted = [...new Set(candidates)]
    const unasked = wanted.filter((candidate) => !isKept(keyOf(base, candidate)) && !asking.has(keyOf(base, candidate)))
    if (unasked.length) {
      if (kept.size >= MAX_KEPT) kept.clear()
      const request = ask(base, unasked)
        .then((answer) => {
          const answeredAt = now()
          for (const candidate of unasked) {
            const found = answer[candidate] ?? null
            kept.set(keyOf(base, candidate), { found, until: answeredAt + (found ? ttl.found : ttl.missing) })
          }
        })
        .finally(() => unasked.forEach((candidate) => asking.delete(keyOf(base, candidate))))
      for (const candidate of unasked) asking.set(keyOf(base, candidate), request)
    }
    await Promise.all(wanted.map((candidate) => asking.get(keyOf(base, candidate))))
    const answer: Record<string, ExistingPath> = {}
    for (const candidate of wanted) {
      const found = kept.get(keyOf(base, candidate))?.found
      if (found) answer[candidate] = found
    }
    return answer
  }
}
