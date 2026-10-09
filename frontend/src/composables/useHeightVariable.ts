import { onBeforeUnmount, useTemplateRef, watch } from 'vue'

/**
 * Keeps the height of an element that sticks to the top or bottom (the app's header and bottom bar,
 * a page's foot) in a CSS variable on the page, e.g. --app-header-height, for what has to keep
 * clear of it. Hidden (the bottom bar on wide screens) it is 0. `refName` is the element's ref in
 * the template.
 */
export function useHeightVariable(variable: string, refName: string): void {
  const element = useTemplateRef<HTMLElement>(refName)
  const resizes = new ResizeObserver(([entry]) => {
    document.documentElement.style.setProperty(variable, `${entry!.borderBoxSize[0]!.blockSize}px`)
  })
  // Also an element that only appears later (v-if).
  watch(element, (shown, gone) => {
    if (gone) resizes.unobserve(gone)
    if (shown) resizes.observe(shown)
  })
  onBeforeUnmount(() => resizes.disconnect())
}
