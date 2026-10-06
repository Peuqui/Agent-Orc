// The formatting bar of a note: each format writes the Markdown for the selection (or the lines
// it touches) into the text. Pure functions, so the edits can be tested without a browser.

export interface Edit {
  text: string
  /** The selection after the edit. */
  from: number
  to: number
}

export type FormatId = 'bold' | 'italic' | 'heading' | 'list' | 'code' | 'link'

/** The text put in where nothing is selected (translated by the caller). */
export type Placeholders = Record<'bold' | 'italic' | 'code' | 'link', string>

export const FORMATS: { id: FormatId; label: string }[] = [
  { id: 'bold', label: 'B' },
  { id: 'italic', label: 'I' },
  { id: 'heading', label: 'H' },
  { id: 'list', label: '•' },
  { id: 'code', label: '</>' },
  { id: 'link', label: '🔗' },
]

export const LINK_ADDRESS = 'https://'
const HEADING_PREFIX = '## '
const LIST_PREFIX = '- '
const CODE_FENCE = '```'

function wrap(text: string, from: number, to: number, mark: string, placeholder: string): Edit {
  const inner = text.slice(from, to) || placeholder
  const start = from + mark.length
  return { text: text.slice(0, from) + mark + inner + mark + text.slice(to), from: start, to: start + inner.length }
}

/** Puts the prefix before every line the selection touches. */
function prefixLines(text: string, from: number, to: number, prefix: string): Edit {
  const start = text.lastIndexOf('\n', from - 1) + 1
  const nextBreak = text.indexOf('\n', to)
  const end = nextBreak === -1 ? text.length : nextBreak
  const block = text
    .slice(start, end)
    .split('\n')
    .map((line) => prefix + line)
    .join('\n')
  return { text: text.slice(0, start) + block + text.slice(end), from: start, to: start + block.length }
}

function code(text: string, from: number, to: number, placeholder: string): Edit {
  const chosen = text.slice(from, to)
  if (!chosen.includes('\n')) return wrap(text, from, to, '`', placeholder)
  const fenceLength = CODE_FENCE.length + 1
  const block = `${CODE_FENCE}\n${chosen}\n${CODE_FENCE}`
  return { text: text.slice(0, from) + block + text.slice(to), from: from + fenceLength, to: from + fenceLength + chosen.length }
}

function link(text: string, from: number, to: number, placeholder: string): Edit {
  const label = text.slice(from, to) || placeholder
  const start = from + label.length + 3
  return {
    text: `${text.slice(0, from)}[${label}](${LINK_ADDRESS})${text.slice(to)}`,
    from: start,
    to: start + LINK_ADDRESS.length,
  }
}

export function applyFormat(id: FormatId, text: string, from: number, to: number, placeholders: Placeholders): Edit {
  switch (id) {
    case 'bold':
      return wrap(text, from, to, '**', placeholders.bold)
    case 'italic':
      return wrap(text, from, to, '*', placeholders.italic)
    case 'heading':
      return prefixLines(text, from, to, HEADING_PREFIX)
    case 'list':
      return prefixLines(text, from, to, LIST_PREFIX)
    case 'code':
      return code(text, from, to, placeholders.code)
    case 'link':
      return link(text, from, to, placeholders.link)
  }
}

/** The Markdown for a file stored for a note: a picture shows in the view, any other file is a link. */
export function fileLink(name: string, url: string, isImage: boolean): string {
  const label = name.replace(/[[\]]/g, '')
  return `${isImage ? '!' : ''}[${label}](${url})`
}

/** Puts a block (a file link) on a line of its own at the cursor, apart from the text around it. */
export function insertBlock(text: string, at: number, block: string): Edit {
  const before = text.slice(0, at)
  const after = text.slice(at)
  const lead = before === '' || before.endsWith('\n\n') ? '' : before.endsWith('\n') ? '\n' : '\n\n'
  const trail = after === '' || after.startsWith('\n\n') ? '' : after.startsWith('\n') ? '\n' : '\n\n'
  const inserted = lead + block + trail
  const caret = before.length + lead.length + block.length + trail.length
  return { text: before + inserted + after, from: caret, to: caret }
}

export interface PdfLink {
  name: string
  url: string
}

/** The PDFs a note links to, in the order they appear (shown below the text as previews). */
export function pdfLinks(text: string): PdfLink[] {
  const links: PdfLink[] = []
  for (const match of text.matchAll(/(?<!!)\[([^\]]*)\]\((api\/notes\/files\/[^)\s]+\.pdf)\)/gi)) {
    links.push({ name: match[1], url: match[2] })
  }
  return links
}
