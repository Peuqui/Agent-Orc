// What is read aloud of an answer: Markdown made into plain sentences, without what cannot be
// listened to (code, tables, addresses), cut into pieces a speech engine takes in one go. Pure
// functions, so they can be tested without a browser.

/** Browsers cut off a long utterance after some seconds; pieces of this size stay safe. */
export const MAX_CHUNK_CHARS = 200

const SENTENCE_END = /(?<=[.!?…:;])\s+/

/**
 * The answer as speakable text. `skipped` is said in place of a code block or a table (in the
 * language of the voice), so the listener knows something was left out.
 */
export function speakableText(markdown: string, skipped: string): string {
  const lines: string[] = []
  let inCode = false
  let inTable = false
  for (const raw of markdown.split('\n')) {
    if (/^\s*```/.test(raw)) {
      inCode = !inCode
      if (inCode) lines.push(skipped + '.')
      continue
    }
    if (inCode) continue
    if (/^\s*\|/.test(raw)) {
      if (!inTable) lines.push(skipped + '.')
      inTable = true
      continue
    }
    inTable = false
    lines.push(plainLine(raw))
  }
  return lines
    .filter((line) => line.trim() !== '')
    .map((line) => (/[.!?…:;]$/.test(line.trim()) ? line.trim() : line.trim() + '.'))
    .join('\n')
}

function plainLine(line: string): string {
  return line
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/https?:\/\/\S+/g, '')
    .replace(/<[^>]+>/g, '')
    .replace(/^\s*#{1,6}\s+/, '')
    .replace(/^\s*[-*+]\s+/, '')
    .replace(/^\s*>\s?/, '')
    .replace(/(\*\*|__|\*|_|`|~~)/g, '')
    .replace(/\s+/g, ' ')
}

/** The text in pieces of at most `max` characters, each ending at a sentence or line end. */
export function speechChunks(text: string, max = MAX_CHUNK_CHARS): string[] {
  const chunks: string[] = []
  for (const line of text.split('\n')) {
    let current = ''
    for (const sentence of line.split(SENTENCE_END)) {
      for (const part of splitLong(sentence.trim(), max)) {
        if (part === '') continue
        if (current !== '' && current.length + 1 + part.length > max) {
          chunks.push(current)
          current = part
        } else {
          current = current === '' ? part : `${current} ${part}`
        }
      }
    }
    if (current !== '') chunks.push(current)
  }
  return chunks
}

/** A sentence longer than the limit is cut at spaces. */
function splitLong(sentence: string, max: number): string[] {
  if (sentence.length <= max) return [sentence]
  const parts: string[] = []
  let current = ''
  for (const word of sentence.split(' ')) {
    if (current !== '' && current.length + 1 + word.length > max) {
      parts.push(current)
      current = word
    } else {
      current = current === '' ? word : `${current} ${word}`
    }
  }
  if (current !== '') parts.push(current)
  return parts
}

/** Agents end an answer with a paragraph for listening, which starts with this (global CLAUDE.md). */
export const LISTEN_MARKER = '🔊'
/** What is read of an answer without such a paragraph: up to this many characters. */
export const DEFAULT_MAX_SPOKEN_CHARS = 900

/** The last paragraph for listening of an answer, without its marker; null if there is none. */
export function listeningParagraph(markdown: string): string | null {
  const paragraphs = markdown.split(/\n\s*\n/).map((paragraph) => paragraph.trim())
  const found = paragraphs.findLast((paragraph) => paragraph.startsWith(LISTEN_MARKER))
  return found === undefined ? null : found.slice(LISTEN_MARKER.length).trim()
}

/** The text cut after its last whole sentence within `max` characters. */
function cutAtSentence(text: string, max: number): string {
  if (text.length <= max) return text
  const head = text.slice(0, max)
  const ends = [...head.matchAll(/[.!?…](?=\s|$)/g)]
  const last = ends.at(-1)
  return last?.index === undefined ? head : head.slice(0, last.index + 1)
}

/**
 * What is spoken of an answer: its paragraph for listening if it has one, otherwise the answer
 * itself, as far as `maxChars` allows (the rest stays to be read in the view).
 */
export function spokenText(markdown: string, skipped: string, maxChars: number): string {
  const listening = listeningParagraph(markdown)
  if (listening !== null) return speakableText(listening, skipped)
  return cutAtSentence(speakableText(markdown, skipped), maxChars)
}
