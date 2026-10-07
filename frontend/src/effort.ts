/**
 * The level an agent or model runs with when the wished one is not among those it takes: the next
 * higher one it takes (as lclaude translates), otherwise its highest. `order` is the profile's
 * list of levels from low to high; none when the agent takes no level.
 */
export function nearestLevel(wanted: string | null, levels: string[], order: string[]): string | null {
  if (levels.length === 0) return null
  if (wanted !== null && levels.includes(wanted)) return wanted
  const rank = order.indexOf(wanted ?? '')
  return levels.find((level) => order.indexOf(level) >= rank) ?? levels[levels.length - 1]
}
