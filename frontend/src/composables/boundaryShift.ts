// Narrowest column a divider can leave, as a share of the screen width.
export const MIN_WIDTH_SHARE = 0.1
// More columns than fit at that width on the screen cannot be shown.
export const MAX_VISIBLE = Math.floor(1 / MIN_WIDTH_SHARE)

/** How far the boundary between two neighbouring columns moves when the divider is dragged by
 *  `moved` (a share of the screen width): what one gains the other loses, and neither gets
 *  narrower than the smallest width. Positive: the left column grows. */
export function boundaryShift(leftShare: number, rightShare: number, moved: number): number {
  return Math.min(rightShare - MIN_WIDTH_SHARE, Math.max(MIN_WIDTH_SHARE - leftShare, moved))
}
