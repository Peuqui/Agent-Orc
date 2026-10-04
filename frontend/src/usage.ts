// From here on a usage is worth noticing (a fresh session or /compact for the context, a
// pause for the account limits).
const WARN_PERCENT = 70
const CRITICAL_PERCENT = 90

/** Colour classes for a usage in percent: bar (background), text and ring (SVG stroke). */
export function usageTone(percent: number): { bar: string; text: string; ring: string } {
  if (percent >= CRITICAL_PERCENT) {
    return { bar: 'bg-red-500', text: 'text-red-400', ring: 'stroke-red-500' }
  }
  if (percent >= WARN_PERCENT) {
    return { bar: 'bg-amber-500', text: 'text-amber-400', ring: 'stroke-orange-600' }
  }
  // The context ring fills in orange from the start, like Claude Code's.
  return { bar: 'bg-slate-400', text: 'text-slate-400', ring: 'stroke-orange-400' }
}
