import { type Ref, nextTick, ref } from 'vue'
import { type Reason, TOP_ROOM_PX, isFollowing, moveFor } from '../feedScroll'

// Where the reader was in the feed of each agent, as the first message in view and how far below the
// upper edge it began: kept while the app is open, so that coming back lands where the reader was.
const remembered = new Map<string, { id: string; offset: number }>()

/**
 * The scrolling of a feed of answers (the rules are in feedScroll.ts). The list's elements carry their
 * message's id in `data-anchor`; `firstUnreadId` says which answer is the oldest unread.
 */
export function useFeedScroll(box: Ref<HTMLElement | undefined>, sessionId: string, firstUnreadId: () => string | undefined) {
  const following = ref(true)
  // Answers that came in while the reader was reading further up.
  const newBelow = ref(0)
  // A reading aloud rolls the list along until the reader scrolls by hand.
  let followsSpeech = true

  const anchor = (id: string): HTMLElement | null => box.value?.querySelector<HTMLElement>(`[data-anchor="${CSS.escape(id)}"]`) ?? null
  const endTop = (scroller: HTMLElement): number => scroller.scrollHeight - scroller.clientHeight

  function toEnd(): void {
    if (box.value) box.value.scrollTo({ top: endTop(box.value) })
  }

  /** Down until the oldest unread answer meets the upper edge, or to the end where what follows fits the screen first. Never up. */
  function toOldestUnread(): void {
    const scroller = box.value
    const id = firstUnreadId()
    const element = id === undefined ? null : anchor(id)
    if (!scroller || element === null) return toEnd()
    const above = element.getBoundingClientRect().top - scroller.getBoundingClientRect().top
    scroller.scrollTo({ top: Math.max(scroller.scrollTop, Math.min(endTop(scroller), scroller.scrollTop + above - TOP_ROOM_PX)) })
  }

  /** Back to where the reader was. */
  function toRemembered(): void {
    const scroller = box.value
    const place = remembered.get(sessionId)
    const element = place === undefined ? null : anchor(place.id)
    if (!scroller || !place || element === null) return toEnd()
    const offsetNow = element.getBoundingClientRect().top - scroller.getBoundingClientRect().top
    scroller.scrollTo({ top: scroller.scrollTop + offsetNow - place.offset })
  }

  /** Something happened (see Reason): the list goes where the rules say, or stays and counts what came in below. */
  async function place(reason: Reason, newAnswers = 0): Promise<void> {
    await nextTick()
    const move = moveFor(reason, { following: following.value, hasUnread: firstUnreadId() !== undefined, hasRemembered: remembered.has(sessionId) })
    if (move === 'end') toEnd()
    else if (move === 'oldestUnread') toOldestUnread()
    else if (move === 'remembered') toRemembered()
    else if (reason === 'answer') newBelow.value += newAnswers
  }

  /** The reader scrolled (or the list moved): following or reading, and where the reader is. */
  function onScroll(): void {
    const scroller = box.value
    if (!scroller) return
    following.value = isFollowing(endTop(scroller) - scroller.scrollTop)
    if (following.value) newBelow.value = 0
    const top = scroller.getBoundingClientRect().top
    const first = [...scroller.querySelectorAll<HTMLElement>('[data-anchor]')].find((element) => element.getBoundingClientRect().bottom > top + 1)
    if (first?.dataset.anchor) remembered.set(sessionId, { id: first.dataset.anchor, offset: first.getBoundingClientRect().top - top })
  }

  /** The reader took the list in hand: a reading aloud no longer rolls it along. */
  function takenByHand(): void {
    followsSpeech = false
  }

  /** The button "↓ N new": down to the oldest unread answer. */
  function showNewBelow(): void {
    toOldestUnread()
    newBelow.value = 0
  }

  /** The answer that is read aloud now comes into view (its top, if it is not wholly in view), until the reader scrolls by hand. */
  function followSpeech(id: string, startsNow: boolean): void {
    if (startsNow) followsSpeech = true
    const scroller = box.value
    const element = anchor(id)
    if (!followsSpeech || !scroller || element === null) return
    const view = scroller.getBoundingClientRect()
    const bounds = element.getBoundingClientRect()
    if (bounds.top >= view.top && bounds.bottom <= view.bottom) return
    scroller.scrollTo({ top: scroller.scrollTop + bounds.top - view.top - TOP_ROOM_PX })
  }

  return { following, newBelow, place, onScroll, takenByHand, showNewBelow, followSpeech }
}
