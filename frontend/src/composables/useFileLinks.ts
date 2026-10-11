import type { IBufferRange, ILink, ILinkProvider, Terminal } from '@xterm/xterm'
import type { Router } from 'vue-router'
import { api, type ExistingPath } from '../api'
import { type PathMention, pathsIn } from '../filePaths'

// Lines asked about lately; enough for a screen and some scrolling.
const MAX_CACHED_LINES = 300

/** A file opens in the editor (at the line, if one is given), a folder in the file view. */
export function openExistingPath(router: Router, target: ExistingPath, line: number | null): void {
  if (target.kind === 'folder') void router.push({ path: '/files', query: { path: target.path } })
  else void router.push({ path: '/edit', query: line === null ? { path: target.path } : { path: target.path, line } })
}

/**
 * Makes the files and folders an agent mentions clickable: a file opens in the editor (at the
 * line, if one is given), a folder in the file view. Only paths that exist are offered.
 */
export function registerFileLinks(terminal: Terminal, router: Router, folder: () => string | undefined): void {
  const asked = new Map<string, Promise<Record<string, ExistingPath>>>()

  function existing(base: string, lineText: string, candidates: PathMention[]): Promise<Record<string, ExistingPath>> {
    const key = `${base}\n${lineText}`
    let answer = asked.get(key)
    if (answer === undefined) {
      if (asked.size >= MAX_CACHED_LINES) asked.clear()
      answer = api.existingPaths(base, [...new Set(candidates.map((candidate) => candidate.text))])
      asked.set(key, answer)
    }
    return answer
  }

  const provider: ILinkProvider = {
    provideLinks(bufferLine, callback) {
      const lineText = terminal.buffer.active.getLine(bufferLine - 1)?.translateToString(true) ?? ''
      const candidates = pathsIn(lineText)
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
              return { range, text: candidate.text, activate: () => openExistingPath(router, found[candidate.text]!, candidate.line) }
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
