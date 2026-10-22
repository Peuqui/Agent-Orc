// How worth noticing a usage is: an account limit from its own shares on (time for a pause); a
// context from a share on that it is filling up, and critical once the server advises its
// handover (shortly before Claude Code compacts it, see handover.py).
const QUOTA_WARN_PERCENT = 50
const QUOTA_CRITICAL_PERCENT = 70
const CONTEXT_WARN_PERCENT = 80

export type UsageLevel = 'normal' | 'warn' | 'critical'

export function quotaLevel(percent: number): UsageLevel {
  if (percent >= QUOTA_CRITICAL_PERCENT) return 'critical'
  return percent >= QUOTA_WARN_PERCENT ? 'warn' : 'normal'
}

export function contextLevel(percent: number, handoverAdvised: boolean): UsageLevel {
  if (handoverAdvised) return 'critical'
  return percent >= CONTEXT_WARN_PERCENT ? 'warn' : 'normal'
}

/** Colour classes for a usage level: bar (background), text and ring (SVG stroke). */
export function usageTone(level: UsageLevel): { bar: string; text: string; ring: string } {
  if (level === 'critical') {
    return { bar: 'bg-red-500', text: 'text-red-400', ring: 'stroke-red-500' }
  }
  // Warning in the amber of the "working" badge.
  if (level === 'warn') {
    return { bar: 'bg-amber-500', text: 'text-amber-400', ring: 'stroke-amber-300' }
  }
  // The context ring is coloured from the start, like Claude Code's.
  return { bar: 'bg-slate-400', text: 'text-slate-400', ring: 'stroke-green-500' }
}
