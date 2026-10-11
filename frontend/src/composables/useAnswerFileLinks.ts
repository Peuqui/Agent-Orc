import { onBeforeUnmount, onMounted, onUpdated, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import type { ExistingPath } from '../api'
import { existingPaths } from '../existingPaths'
import { MISSING_TTL_MS } from '../pathLookup'
import { pathOfCode } from '../filePaths'
import { openExistingPath } from './useFileLinks'

/** Class of a piece of code in an answer that names an existing file or folder (style.css). */
export const FILE_LINK_CLASS = 'file-link'
// What the code stands for, kept on the element for the click.
const FILE_ATTRIBUTE = 'data-file-path'
const KIND_ATTRIBUTE = 'data-file-kind'
const LINE_ATTRIBUTE = 'data-file-line'
const CHECKED_ATTRIBUTE = 'data-file-checked'
// A path that does not exist yet (the agent names a file before it has written it) is looked at
// again this often, this many times after each change of the answers; then it is left alone.
const RECHECK_ROUNDS = 12

/**
 * Makes the files and folders an agent names in its answers clickable, as in its terminal (see
 * useFileLinks): a piece of code (`docs/TODO.md`, `src/app.py:42`) that is a path, and exists in
 * the agent's folder, opens the file in the editor (at the line) or the folder in the file view.
 * `root` holds the answers, which come as HTML text: the pieces of code are looked at after each
 * change, and one click listener on `root` answers them.
 */
export function useAnswerFileLinks(root: Ref<HTMLElement | undefined>, folder: () => string | undefined): void {
  const router = useRouter()
  let recheck: number | undefined
  let rounds = 0

  async function mark(): Promise<void> {
    const base = folder()
    const element = root.value
    if (base === undefined || element === undefined) return
    const unchecked = [...element.querySelectorAll<HTMLElement>(`.markdown :not(pre) > code:not([${CHECKED_ATTRIBUTE}])`)]
    const mentions = unchecked.map((code) => ({ code, path: pathOfCode(code.textContent ?? '') }))
    let found: Record<string, ExistingPath>
    try {
      found = await existingPaths(base, mentions.flatMap(({ path }) => (path ? [path.text] : [])))
    } catch (error) {
      // No links this time (e.g. the login expired); the next change asks again.
      console.error('looking up file links failed', error)
      return
    }
    let missing = 0
    for (const { code, path } of mentions) {
      const target = path === null ? undefined : found[path.text]
      // Code that is no path is done with; a path that is not there yet is looked at again.
      if (path === null || target === undefined) {
        if (path === null) code.setAttribute(CHECKED_ATTRIBUTE, '')
        else missing++
        continue
      }
      code.setAttribute(CHECKED_ATTRIBUTE, '')
      code.classList.add(FILE_LINK_CLASS)
      code.setAttribute(FILE_ATTRIBUTE, target.path)
      code.setAttribute(KIND_ATTRIBUTE, target.kind)
      if (path.line !== null) code.setAttribute(LINE_ATTRIBUTE, String(path.line))
    }
    window.clearTimeout(recheck)
    if (missing > 0 && rounds < RECHECK_ROUNDS) {
      rounds++
      recheck = window.setTimeout(() => void mark(), MISSING_TTL_MS)
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
  onUpdated(() => {
    rounds = 0
    void mark()
  })
  onBeforeUnmount(() => {
    window.clearTimeout(recheck)
    root.value?.removeEventListener('click', onClick)
  })
}
