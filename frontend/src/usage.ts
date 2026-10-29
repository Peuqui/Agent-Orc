// How worth noticing a usage is: an account limit from its own shares on (time for a pause); a
// context from a share on that it is filling up, and critical once its handover is due (shortly
// before Claude Code compacts it, see handover.py).
const QUOTA_WARN_PERCENT = 50
const QUOTA_CRITICAL_PERCENT = 70
const CONTEXT_WARN_PERCENT = 80

export type UsageLevel = 'normal' | 'warn' | 'critical'

export function quotaLevel(percent: number): UsageLevel {
  if (percent >= QUOTA_CRITICAL_PERCENT) return 'critical'
  return percent >= QUOTA_WARN_PERCENT ? 'warn' : 'normal'
}

export function contextLevel(percent: number, handoverDue: boolean): UsageLevel {
  if (handoverDue) return 'critical'
  return percent >= CONTEXT_WARN_PERCENT ? 'warn' : 'normal'
}

/** Colour classes for a usage level: bar (background), text and ring (SVG stroke). */
export function usageTone(level: UsageLevel): { bar: string; text: string; ring: string } {
  if (level === 'critical') {
    return { bar: 'bg-accent-500', text: 'text-accent-400', ring: 'stroke-accent-500' }
  }
  // Warning in the amber of the "working" badge.
  if (level === 'warn') {
    return { bar: 'bg-highlight-500', text: 'text-highlight-400', ring: 'stroke-highlight-300' }
  }
  // The context ring is coloured from the start, like Claude Code's.
  return { bar: 'bg-dim', text: 'text-dim', ring: 'stroke-ok-400' }
}
