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
 * lineBreaks: a single line break in the text stays one in the page (notes), instead of
 * merging the lines into a paragraph.
 */
export function renderMarkdown(text: string, filePath: string, lineBreaks = false): string {
  const marked = new Marked({
    gfm: true,
    breaks: lineBreaks,
    walkTokens(token) {
      if (token.type === 'image' && !isExternal(token.href)) {
        token.href = rawFileUrl(linkedPath(filePath, token.href))
      }
    },
  })
  return DOMPurify.sanitize(marked.parse(text, { async: false }))
}
