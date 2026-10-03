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

/** Seconds as "m:ss", e.g. 476 → "7:56". */
export function formatCountdown(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds))
  const minutes = Math.floor(whole / SECONDS_PER_MINUTE)
  return `${minutes}:${String(whole % SECONDS_PER_MINUTE).padStart(2, '0')}`
}
