import { onBeforeUnmount, onMounted, type Ref } from 'vue'

// Marks a modal overlay (BaseDialog, the help): a dialog opened from within a menu is drawn into
// <body>, outside the menu, yet a press in it must not close the menu (and the dialog with it).
export const MODAL_ATTRIBUTE = 'data-modal'

/**
 * Closes a pop-up menu when the user turns elsewhere: a press outside root, Escape, or the
 * window losing the focus — a press into an embedded page (a workspace column) or from there
 * into the surrounding one reaches only that page's document.
 */
export function useDismiss(
  root: Readonly<Ref<HTMLElement | null | undefined>>,
  isOpen: () => boolean,
  close: () => void,
): void {
  /** In a dialog opened from the menu, a press or Escape belongs to that dialog. */
  function inModal(target: EventTarget | null): boolean {
    return target instanceof Element && target.closest(`[${MODAL_ATTRIBUTE}]`) !== null
  }

  function onPointerDown(event: PointerEvent): void {
    if (!isOpen() || !(event.target instanceof Node)) return
    if (root.value?.contains(event.target) || inModal(event.target)) return
    close()
  }

  function onKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Escape' && isOpen() && !inModal(event.target)) close()
  }

  function onBlur(): void {
    if (isOpen()) close()
  }

  onMounted(() => {
    document.addEventListener('pointerdown', onPointerDown, true)
    document.addEventListener('keydown', onKeyDown)
    window.addEventListener('blur', onBlur)
  })
  onBeforeUnmount(() => {
    document.removeEventListener('pointerdown', onPointerDown, true)
    document.removeEventListener('keydown', onKeyDown)
    window.removeEventListener('blur', onBlur)
  })
}
