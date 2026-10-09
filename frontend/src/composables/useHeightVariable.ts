import { onBeforeUnmount, onMounted, useTemplateRef } from 'vue'

/**
 * Keeps the height of an element of the app's frame (header, bottom bar) in a CSS variable on the
 * page, e.g. --app-header-height, for what sticks to a page's top or bottom next to it. Hidden
 * (the bottom bar on wide screens) it is 0. `refName` is the element's ref in the template.
 */
export function useHeightVariable(variable: string, refName: string): void {
  const element = useTemplateRef<HTMLElement>(refName)
  const resizes = new ResizeObserver(([entry]) => {
    document.documentElement.style.setProperty(variable, `${entry!.borderBoxSize[0]!.blockSize}px`)
  })
  onMounted(() => element.value && resizes.observe(element.value))
  onBeforeUnmount(() => resizes.disconnect())
}
