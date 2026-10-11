// Paths as agents write them: absolute, from ~, ./ or ../, or relative, folders also with a
// closing slash; ":42" names a line.
// Not inside a word or a URL (the lookbehind), and only those with a folder or an extension
// are asked about, so plain words are left alone. A hidden name may follow a slash (~/.config).
const PATH_SOURCE = String.raw`(?<![\w./~:@+-])((?:~|\.{1,2})?\/?(?:[\w@+-]|(?<=\/)\.)[\w.@+-]*(?:\/[\w.@+-]+)*\/?)(?::(\d+))?`
const PATH = new RegExp(PATH_SOURCE, 'g')
const WHOLE_PATH = new RegExp(`^${PATH_SOURCE}$`)
const LOOKS_LIKE_A_PATH = /\/|\.[A-Za-z0-9]{1,10}$/

export interface PathMention {
  /** The path as written, without a line number and without a full stop after it. */
  text: string
  /** The line named after a colon. */
  line: number | null
  /** Where it starts in the text. */
  start: number
}

/** The paths a line of text mentions (to be asked about: which of them exist). */
export function pathsIn(lineText: string): PathMention[] {
  const found: PathMention[] = []
  for (const match of lineText.matchAll(PATH)) {
    // A full stop or comma after a path belongs to the sentence.
    const text = match[1]!.replace(/[.,]+$/, '')
    if (LOOKS_LIKE_A_PATH.test(text)) {
      found.push({ text, line: match[2] ? Number(match[2]) : null, start: match.index })
    }
  }
  return found
}

/** What a piece of code says, if all of it is a path (e.g. `docs/TODO.md:42`); otherwise null. */
export function pathOfCode(code: string): PathMention | null {
  const text = code.trim()
  const match = WHOLE_PATH.exec(text)
  if (match === null || !LOOKS_LIKE_A_PATH.test(match[1]!)) return null
  return { text: match[1]!, line: match[2] ? Number(match[2]) : null, start: 0 }
}
