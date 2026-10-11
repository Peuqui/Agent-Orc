import { type Ref, computed, nextTick, watch } from 'vue'
import { DEFAULT_FONT_SIZE, useSettings } from './useSettings'

// How far below the top edge of what is in view the anchor text is taken (inside its first line).
const ANCHOR_OFFSET_PX = 4

/** Where the part of a scroller that is in view begins: below the app's header on a page that
 * scrolls as a whole, else at the scroller's own top. */
function visibleTop(root: HTMLElement): number {
  if (root !== document.scrollingElement) return root.getBoundingClientRect().top
  return parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--app-header-height')) || 0
}

/** The top of the text a range starts at (a collapsed range has no box, so one letter is taken). */
function textTop(range: Range): number {
  const letter = range.cloneRange()
  const node = letter.startContainer
  if (node.nodeType === Node.TEXT_NODE && letter.startOffset < (node.textContent?.length ?? 0)) {
    letter.setEnd(node, letter.startOffset + 1)
  }
  return letter.getBoundingClientRect().top
}

/** The first index in 0..length that `isBelow` accepts, given that what it accepts is a tail. */
function firstBelow(length: number, isBelow: (index: number) => boolean): number {
  let low = 0
  let high = length
  while (low < high) {
    const middle = (low + high) >> 1
    if (isBelow(middle)) high = middle
    else low = middle + 1
  }
  return low
}

/** The first letter of `element` whose line ends below `edge`: where the reader is. Found by
 * the text's geometry, not by what is drawn at the edge (a menu may be open above it). */
function letterBelow(element: HTMLElement, edge: number): Range | null {
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => (node.textContent?.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT),
  })
  const texts: Text[] = []
  for (let node = walker.nextNode(); node; node = walker.nextNode()) texts.push(node as Text)
  const letterRange = (text: Text, offset: number): Range => {
    const range = document.createRange()
    range.setStart(text, offset)
    range.setEnd(text, Math.min(offset + 1, text.length))
    return range
  }
  const endsBelow = (range: Range): boolean => range.getBoundingClientRect().bottom > edge
  const index = firstBelow(texts.length, (i) => endsBelow(letterRange(texts[i]!, texts[i]!.length - 1)))
  const text = texts[index]
  if (!text) return null
  const offset = firstBelow(text.length, (i) => endsBelow(letterRange(text, i)))
  return letterRange(text, offset)
}

/**
 * The views' font size as a zoom: what a view shows is scaled as a whole, so all its sizes keep
 * their proportions (its texts are set in rem, which a font size on the element would not reach).
 * `content` is the zoomed element, `scroller` the element it scrolls in (the page itself when
 * not given). A change keeps what is in view in view: the text at the top edge stays there. A
 * factor on the scroll position would not do, larger text also wraps into more lines.
 */
export function useViewZoom(content: Ref<HTMLElement | undefined>, scroller?: Ref<HTMLElement | undefined>) {
  const { viewFontSize } = useSettings()
  const zoomStyle = computed(() => ({ zoom: viewFontSize.value / DEFAULT_FONT_SIZE }))

  // Before the change reaches the page, while the text is still where it was.
  watch(
    zoomStyle,
    () => {
      const element = content.value
      const root = scroller?.value ?? (document.scrollingElement as HTMLElement)
      if (!element) return
      const edge = visibleTop(root) + ANCHOR_OFFSET_PX
      const anchor = letterBelow(element, edge)
      // Nothing of the content is below the edge: nothing to keep.
      if (!anchor) return
      const offset = textTop(anchor) - edge
      void nextTick(() => {
        root.scrollTop += textTop(anchor) - edge - offset
      })
    },
    { flush: 'pre' },
  )

  return { zoomStyle }
}
