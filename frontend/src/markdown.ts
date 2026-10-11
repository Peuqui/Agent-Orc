import DOMPurify from 'dompurify'
import { Marked } from 'marked'
import { rawFileUrl } from './api'
import { joinPath, parentPath } from './format'
import { i18n } from './i18n'
import { ICONS } from './icons'

// A scheme (https:, mailto:, data:) or protocol-relative: not a path in the project.
const EXTERNAL = /^([a-z][a-z0-9+.-]*:|\/\/)/i

export function isExternal(href: string): boolean {
  return EXTERNAL.test(href)
}

/** Where a relative link or picture of a Markdown file points to; anchors and queries dropped. */
export function linkedPath(filePath: string, href: string): string {
  return joinPath(parentPath(filePath), href.split(/[?#]/)[0])
}

/** The block around a code block and its copy button, and the button (styled in style.css). */
export const CODE_BLOCK_CLASS = 'code-block'
export const CODE_COPY_CLASS = 'code-copy'

/** Every code block gets a button that copies it (useCodeCopy answers its click): selecting
 * exactly the letters on a phone is fiddly. */
function withCopyButtons(html: string): string {
  const page = new DOMParser().parseFromString(html, 'text/html')
  const label = i18n.global.t('markdown.copyCode')
  for (const block of page.querySelectorAll('pre')) {
    const wrapper = page.createElement('div')
    wrapper.className = CODE_BLOCK_CLASS
    const button = page.createElement('button')
    button.type = 'button'
    button.className = CODE_COPY_CLASS
    button.title = label
    button.setAttribute('aria-label', label)
    button.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${ICONS.copy}"/></svg>`
    block.replaceWith(wrapper)
    wrapper.append(block, button)
  }
  return page.body.innerHTML
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
  return withCopyButtons(DOMPurify.sanitize(html))
}
