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

/**
 * Token counts in short form, with the language's own units (`units`: thousand, million, billion,
 * ...; German counts in steps of a thousand too, but its billion is a million millions): 950,
 * 675k, 1.2M or 675 Tsd., 1,2 Mio. Thousands are rounded, larger units get one decimal.
 */
export function formatTokens(tokens: number, units: string[], locale: string): string {
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 })
  let value = tokens
  let unit = -1
  while (unit < units.length - 1 && Math.round(value) >= THOUSAND) {
    value /= THOUSAND
    unit += 1
  }
  if (unit === -1) return number.format(value)
  const rounded = unit === 0 ? Math.round(value) : Number(value.toFixed(1))
  return `${number.format(rounded)}${units[unit]}`
}

const MINUTES_PER_HOUR = 60

/** A span in whole minutes: "42 min", from an hour on "1 h 5 min" ("0 min" under a minute). */
export function formatMinutes(seconds: number): string {
  const minutes = Math.floor(Math.max(0, seconds) / SECONDS_PER_MINUTE)
  if (minutes < MINUTES_PER_HOUR) return `${minutes} min`
  const hours = Math.floor(minutes / MINUTES_PER_HOUR)
  const rest = minutes % MINUTES_PER_HOUR
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`
}

/** Seconds as "m:ss", e.g. 476 → "7:56". */
export function formatCountdown(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds))
  const minutes = Math.floor(whole / SECONDS_PER_MINUTE)
  return `${minutes}:${String(whole % SECONDS_PER_MINUTE).padStart(2, '0')}`
}
