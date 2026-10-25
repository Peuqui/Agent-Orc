import { onBeforeUnmount, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { CODE_COPY_CLASS } from '../markdown'
import { FILE_LINK_CLASS } from './useAnswerFileLinks'
import { useCopyText } from './useCopyText'

// Code in the running text of rendered Markdown (answers, notes, previews), not in a block.
const INLINE_CODE = '.markdown :not(pre) > code'

/** Answers a click on the copy button of a code block (see markdown.ts) and on code in the running
 * text, which it copies too, wherever one is shown: one listener on the page, as the Markdown comes
 * as HTML text. A path that opens its file (FILE_LINK_CLASS) opens it, and a click that ends a
 * selection leaves the selection alone. */
export function useCodeCopy(): void {
  const copyText = useCopyText()
  const { t } = useI18n()

  function onClick(event: MouseEvent): void {
    if (!(event.target instanceof Element)) return
    const inline = event.target.closest(INLINE_CODE)
    if (inline && !inline.classList.contains(FILE_LINK_CLASS) && window.getSelection()?.isCollapsed !== false) {
      void copyText(inline.textContent ?? '', t('terminal.copied'))
      return
    }
    const button = event.target.closest(`.${CODE_COPY_CLASS}`)
    if (!button) return
    // Without the line break at the end: pasted into a terminal it would run the command at once.
    const code = button.parentElement?.querySelector('pre')?.textContent ?? ''
    void copyText(code.replace(/\n$/, ''), t('terminal.copied'))
  }

  onMounted(() => document.addEventListener('click', onClick))
  onBeforeUnmount(() => document.removeEventListener('click', onClick))
}
