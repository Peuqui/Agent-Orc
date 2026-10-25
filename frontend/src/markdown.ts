import DOMPurify from 'dompurify'
import { Marked } from 'marked'
import { rawFileUrl } from './api'
import { joinPath, parentPath } from './format'
import { i18n } from './i18n'
import { ICONS } from './icons'
import { LISTEN_MARKER } from './speechText'

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

/** Links to other sites open in a tab of their own (in the installed app: the system's browser).
 * In the page itself they would replace the app, and in a workspace column most sites refuse to be
 * shown inside another page ("refused to connect"). Views that handle link clicks themselves (editor,
 * notes) are not affected. */
function withExternalLinksOutside(html: string): string {
  const page = new DOMParser().parseFromString(html, 'text/html')
  for (const link of page.querySelectorAll('a[href]')) {
    if (!isExternal(link.getAttribute('href') ?? '')) continue
    link.setAttribute('target', '_blank')
    link.setAttribute('rel', 'noopener noreferrer')
  }
  return page.body.innerHTML
}

/** The marker of the paragraph for listening, as a button that reads the paragraph again (the view answers its click). */
export const LISTEN_REPLAY_CLASS = 'listen-replay'

/** The marker in front of the last paragraph for listening becomes that button; the rest of the page stays as it is. */
function withReplayButton(html: string): string {
  const page = new DOMParser().parseFromString(html, 'text/html')
  const paragraph = [...page.querySelectorAll('p')].findLast((candidate) => candidate.textContent?.trimStart().startsWith(LISTEN_MARKER))
  const text = paragraph?.firstChild
  if (!paragraph || text?.nodeType !== Node.TEXT_NODE) return html
  const label = i18n.global.t('answers.readAgain')
  const button = page.createElement('button')
  button.type = 'button'
  button.className = LISTEN_REPLAY_CLASS
  button.title = label
  button.setAttribute('aria-label', label)
  button.textContent = LISTEN_MARKER
  text.textContent = (text.textContent ?? '').trimStart().slice(LISTEN_MARKER.length)
  paragraph.prepend(button)
  return page.body.innerHTML
}

/**
 * Markdown as HTML that runs nothing; pictures with relative paths come from the file's folder.
 * filePath null: a note, which has no file, so pictures stay as written (its own files are linked
 * by address) and a single line break in the text stays one in the page instead of merging the
 * lines into a paragraph. `listenButton`: the marker of the paragraph for listening is a button (answers).
 */
export function renderMarkdown(text: string, filePath: string | null, listenButton = false): string {
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
  const page = withExternalLinksOutside(withCopyButtons(DOMPurify.sanitize(html)))
  return listenButton ? withReplayButton(page) : page
}
