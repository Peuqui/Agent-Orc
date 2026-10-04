import type { IBufferRange, ILink, ILinkProvider, Terminal } from '@xterm/xterm'
import type { Router } from 'vue-router'
import { api, type ExistingPath } from '../api'

// Paths as agents write them: absolute, from ~, ./ or ../, or relative, folders also with a
// closing slash; ":42" names a line.
// Not inside a word or a URL (the lookbehind), and only those with a folder or an extension
// are asked about, so plain words are left alone.
const PATH = /(?<![\w./~:@+-])((?:~|\.{1,2})?\/?[\w@+-][\w.@+-]*(?:\/[\w.@+-]+)*\/?)(?::(\d+))?/g
const LOOKS_LIKE_A_PATH = /\/|\.[A-Za-z0-9]{1,10}$/
// Lines asked about lately; enough for a screen and some scrolling.
const MAX_CACHED_LINES = 300

interface Candidate {
  text: string
  line: number | null
  start: number
}

function candidatesIn(lineText: string): Candidate[] {
  const found: Candidate[] = []
  for (const match of lineText.matchAll(PATH)) {
    // A full stop or comma after a path belongs to the sentence.
    const text = match[1].replace(/[.,]+$/, '')
    if (LOOKS_LIKE_A_PATH.test(text)) {
      found.push({ text, line: match[2] ? Number(match[2]) : null, start: match.index })
    }
  }
  return found
}

/**
 * Makes the files and folders an agent mentions clickable: a file opens in the editor (at the
 * line, if one is given), a folder in the file view. Only paths that exist are offered.
 */
export function registerFileLinks(terminal: Terminal, router: Router, folder: () => string | undefined): void {
  const asked = new Map<string, Promise<Record<string, ExistingPath>>>()

  function existing(base: string, lineText: string, candidates: Candidate[]): Promise<Record<string, ExistingPath>> {
    const key = `${base}\n${lineText}`
    let answer = asked.get(key)
    if (answer === undefined) {
      if (asked.size >= MAX_CACHED_LINES) asked.clear()
      answer = api.existingPaths(base, [...new Set(candidates.map((candidate) => candidate.text))])
      asked.set(key, answer)
    }
    return answer
  }

  function open(target: ExistingPath, line: number | null): void {
    if (target.kind === 'folder') void router.push({ path: '/files', query: { path: target.path } })
    else void router.push({ path: '/edit', query: line === null ? { path: target.path } : { path: target.path, line } })
  }

  const provider: ILinkProvider = {
    provideLinks(bufferLine, callback) {
      const lineText = terminal.buffer.active.getLine(bufferLine - 1)?.translateToString(true) ?? ''
      const candidates = candidatesIn(lineText)
      const base = folder()
      if (base === undefined || candidates.length === 0) {
        callback(undefined)
        return
      }
      existing(base, lineText, candidates)
        .then((found) => {
          const links: ILink[] = candidates
            .filter((candidate) => found[candidate.text] !== undefined)
            .map((candidate) => {
              const length = candidate.text.length + (candidate.line === null ? 0 : String(candidate.line).length + 1)
              const range: IBufferRange = {
                start: { x: candidate.start + 1, y: bufferLine },
                end: { x: candidate.start + length, y: bufferLine },
              }
              return { range, text: candidate.text, activate: () => open(found[candidate.text], candidate.line) }
            })
          callback(links.length ? links : undefined)
        })
        // A failed lookup (e.g. the login expired) only means no links on this line; xterm.js
        // needs its answer either way. Logged, as a toast would come with every hover.
        .catch((error: unknown) => {
          console.error('looking up file links failed', error)
          callback(undefined)
        })
    },
  }
  terminal.registerLinkProvider(provider)
}
