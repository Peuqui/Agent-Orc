// Where the feed of answers goes when something happens. One place for the rules and their numbers; the
// movement itself is in composables/useFeedScroll.ts.
//
// The reader is either FOLLOWING (at the bottom, or has just been brought there) or READING (has scrolled
// up). Following is decided by the reader's own scrolling alone, never by a measurement before each look:
//   - Following: what is new comes into view. A long new answer starts at its top, so that reading can
//     begin at once; a short one ends flush at the bottom.
//   - Reading: nothing moves; a button says what came in below.
// Opening the feed: to the oldest unread answer; with nothing unread, to where the reader was; else the end.

/** The reader is following within this distance (px) of the end of the list. */
export const FOLLOW_WITHIN_PX = 80
/** The room kept above an answer that is read from its top: the padding of the list. */
export const TOP_ROOM_PX = 12

export type Reason = 'opened' | 'own' | 'answer'
export type Move = 'end' | 'oldestUnread' | 'remembered' | 'stay'

export interface Situation {
  following: boolean
  hasUnread: boolean
  hasRemembered: boolean
}

export function isFollowing(distanceFromEnd: number): boolean {
  return distanceFromEnd <= FOLLOW_WITHIN_PX
}

/** What the feed does: `opened` the feed was opened, `own` the reader sent something, `answer` the agent wrote. */
export function moveFor(reason: Reason, situation: Situation): Move {
  if (reason === 'opened') {
    if (situation.hasUnread) return 'oldestUnread'
    return situation.hasRemembered ? 'remembered' : 'end'
  }
  if (!situation.following) return 'stay'
  if (reason === 'own') return 'end'
  return situation.hasUnread ? 'oldestUnread' : 'end'
}
