import { onBeforeUnmount, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { CODE_COPY_CLASS } from '../markdown'
import { useCopyText } from './useCopyText'

/** Answers a click on the copy button of a code block (see markdown.ts), wherever one is shown:
 * one listener on the page, as the blocks come as HTML text. */
export function useCodeCopy(): void {
  const copyText = useCopyText()
  const { t } = useI18n()

  function onClick(event: MouseEvent): void {
    if (!(event.target instanceof Element)) return
    const button = event.target.closest(`.${CODE_COPY_CLASS}`)
    if (!button) return
    // Without the line break at the end: pasted into a terminal it would run the command at once.
    const code = button.parentElement?.querySelector('pre')?.textContent ?? ''
    void copyText(code.replace(/\n$/, ''), t('terminal.copied'))
  }

  onMounted(() => document.addEventListener('click', onClick))
  onBeforeUnmount(() => document.removeEventListener('click', onClick))
}
