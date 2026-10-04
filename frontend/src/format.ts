const SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB']
const BYTES_PER_UNIT = 1024
const SECONDS_PER_MINUTE = 60

export function baseName(path: string): string {
  return path.split('/').filter(Boolean).pop() ?? '/'
}

export function parentPath(path: string): string {
  const parts = path.split('/').filter(Boolean)
  parts.pop()
  return `/${parts.join('/')}`
}

/** A path written relative to a folder (with ./ and ../), or absolute, as an absolute path. */
export function joinPath(folder: string, written: string): string {
  const parts = written.startsWith('/') ? [] : folder.split('/').filter(Boolean)
  for (const part of written.split('/')) {
    if (part === '..') parts.pop()
    else if (part !== '.' && part !== '') parts.push(part)
  }
  return `/${parts.join('/')}`
}

export function formatSize(bytes: number): string {
  let value = bytes
  let unit = 0
  while (value >= BYTES_PER_UNIT && unit < SIZE_UNITS.length - 1) {
    value /= BYTES_PER_UNIT
    unit += 1
  }
  return `${unit === 0 ? value : value.toFixed(1)} ${SIZE_UNITS[unit]}`
}

export function formatDate(date: Date, locale: string): string {
  return date.toLocaleString(locale, { dateStyle: 'short', timeStyle: 'short' })
}

/** A coming moment, as short as it can be: the time today, otherwise weekday and time. */
export function formatMoment(date: Date, locale: string): string {
  const sameDay = date.toDateString() === new Date().toDateString()
  return date.toLocaleString(
    locale,
    sameDay ? { timeStyle: 'short' } : { weekday: 'short', hour: '2-digit', minute: '2-digit' },
  )
}

const THOUSAND = 1000
const MILLION = 1_000_000
const BILLION = 1_000_000_000

/** Token counts in short form: 950, 675k, 1M, 1.2M. */
export function formatTokens(tokens: number): string {
  if (tokens >= BILLION) return `${Number((tokens / BILLION).toFixed(1))}B`
  if (tokens >= MILLION) return `${Number((tokens / MILLION).toFixed(1))}M`
  if (tokens >= THOUSAND) return `${Math.round(tokens / THOUSAND)}k`
  return String(tokens)
}

/** Seconds as "m:ss", e.g. 476 → "7:56". */
export function formatCountdown(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds))
  const minutes = Math.floor(whole / SECONDS_PER_MINUTE)
  return `${minutes}:${String(whole % SECONDS_PER_MINUTE).padStart(2, '0')}`
}
