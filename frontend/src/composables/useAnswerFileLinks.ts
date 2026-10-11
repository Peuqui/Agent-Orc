import { onBeforeUnmount, onMounted, onUpdated, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, type ExistingPath } from '../api'
import { pathOfCode } from '../filePaths'
import { openExistingPath } from './useFileLinks'

/** Class of a piece of code in an answer that names an existing file or folder (style.css). */
export const FILE_LINK_CLASS = 'file-link'
// What the code stands for, kept on the element for the click.
const FILE_ATTRIBUTE = 'data-file-path'
const KIND_ATTRIBUTE = 'data-file-kind'
const LINE_ATTRIBUTE = 'data-file-line'
const CHECKED_ATTRIBUTE = 'data-file-checked'

/**
 * Makes the files and folders an agent names in its answers clickable, as in its terminal (see
 * useFileLinks): a piece of code (`docs/TODO.md`, `src/app.py:42`) that is a path, and exists in
 * the agent's folder, opens the file in the editor (at the line) or the folder in the file view.
 * `root` holds the answers, which come as HTML text: the pieces of code are looked at after each
 * change, and one click listener on `root` answers them.
 */
export function useAnswerFileLinks(root: Ref<HTMLElement | undefined>, folder: () => string | undefined): void {
  const router = useRouter()
  // What the server said about a path, per folder: asked once, not at every change.
  const known = new Map<string, ExistingPath | null>()

  async function mark(): Promise<void> {
    const base = folder()
    const element = root.value
    if (base === undefined || element === undefined) return
    const unchecked = [...element.querySelectorAll<HTMLElement>(`.markdown :not(pre) > code:not([${CHECKED_ATTRIBUTE}])`)]
    const mentions = unchecked.map((code) => ({ code, path: pathOfCode(code.textContent ?? '') }))
    const unasked = [
      ...new Set(mentions.flatMap(({ path }) => (path && !known.has(`${base}\n${path.text}`) ? [path.text] : []))),
    ]
    if (unasked.length) {
      try {
        const found = await api.existingPaths(base, unasked)
        for (const text of unasked) known.set(`${base}\n${text}`, found[text] ?? null)
      } catch (error) {
        // No links this time (e.g. the login expired); the next change asks again.
        console.error('looking up file links failed', error)
        return
      }
    }
    for (const { code, path } of mentions) {
      code.setAttribute(CHECKED_ATTRIBUTE, '')
      const target = path === null ? null : known.get(`${base}\n${path.text}`)
      if (path === null || !target) continue
      code.classList.add(FILE_LINK_CLASS)
      code.setAttribute(FILE_ATTRIBUTE, target.path)
      code.setAttribute(KIND_ATTRIBUTE, target.kind)
      if (path.line !== null) code.setAttribute(LINE_ATTRIBUTE, String(path.line))
    }
  }

  function onClick(event: MouseEvent): void {
    if (!(event.target instanceof Element) || window.getSelection()?.isCollapsed === false) return
    const code = event.target.closest<HTMLElement>(`.${FILE_LINK_CLASS}`)
    const path = code?.getAttribute(FILE_ATTRIBUTE)
    if (!code || !path) return
    const line = code.getAttribute(LINE_ATTRIBUTE)
    const kind = code.getAttribute(KIND_ATTRIBUTE) === 'folder' ? 'folder' : 'file'
    openExistingPath(router, { path, kind }, line === null ? null : Number(line))
  }

  onMounted(() => {
    root.value?.addEventListener('click', onClick)
    void mark()
  })
  onUpdated(() => void mark())
  onBeforeUnmount(() => root.value?.removeEventListener('click', onClick))
}
