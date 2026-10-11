// Narrowest column a divider can leave, as a share of the screen width.
export const MIN_WIDTH_SHARE = 0.1

/** How far the boundary between two neighbouring columns moves when the divider is dragged by
 *  `moved` (a share of the screen width): what one gains the other loses, and neither gets
 *  narrower than the smallest width. Positive: the left column grows. */
export function boundaryShift(leftShare: number, rightShare: number, moved: number): number {
  return Math.min(rightShare - MIN_WIDTH_SHARE, Math.max(MIN_WIDTH_SHARE - leftShare, moved))
}
