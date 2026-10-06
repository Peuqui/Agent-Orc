import DOMPurify from 'dompurify'
import { Marked } from 'marked'
import { rawFileUrl } from './api'
import { joinPath, parentPath } from './format'

// A scheme (https:, mailto:, data:) or protocol-relative: not a path in the project.
const EXTERNAL = /^([a-z][a-z0-9+.-]*:|\/\/)/i

export function isExternal(href: string): boolean {
  return EXTERNAL.test(href)
}

/** Where a relative link or picture of a Markdown file points to; anchors and queries dropped. */
export function linkedPath(filePath: string, href: string): string {
  return joinPath(parentPath(filePath), href.split(/[?#]/)[0])
}

/**
 * Markdown as HTML that runs nothing; pictures with relative paths come from the file's folder.
 * filePath null: a note, which has no file, so pictures stay as written (its own files are linked
 * by address) and a single line break in the text stays one in the page instead of merging the
 * lines into a paragraph.
 */
export function renderMarkdown(text: string, filePath: string | null): string {
  const isNote = filePath === null
  const marked = new Marked({
    gfm: true,
    breaks: isNote,
    walkTokens(token) {
      if (!isNote && token.type === 'image' && !isExternal(token.href)) {
        token.href = rawFileUrl(linkedPath(filePath, token.href))
      }
    },
  })
  const html = marked.parse(text, { async: false })
  return DOMPurify.sanitize(html)
}
