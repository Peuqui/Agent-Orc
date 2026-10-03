import { ref } from 'vue'
import { ApiError } from '../api'
import { i18n } from '../i18n'

export interface Toast {
  id: number
  text: string
  kind: 'error' | 'info'
}

const TOAST_MILLISECONDS = 5000
const SECONDS_PER_MINUTE = 60

const toasts = ref<Toast[]>([])
let nextId = 1

function show(text: string, kind: Toast['kind']): void {
  const id = nextId++
  toasts.value.push({ id, text, kind })
  setTimeout(() => dismiss(id), TOAST_MILLISECONDS)
}

function dismiss(id: number): void {
  toasts.value = toasts.value.filter((toast) => toast.id !== id)
}

/** Translate an API error by its code; unknown codes show the server's detail text. */
function errorText(error: unknown): string {
  if (!(error instanceof ApiError)) return String(error)
  const key = `errors.${error.code}`
  if (!i18n.global.te(key)) return error.message
  const minutes = Math.ceil((error.retryAfterSeconds ?? 0) / SECONDS_PER_MINUTE)
  return i18n.global.t(key, { minutes })
}

function clear(): void {
  toasts.value = []
}

export function useToast() {
  return {
    toasts,
    dismiss,
    clear,
    info: (text: string) => show(text, 'info'),
    error: (error: unknown) => show(errorText(error), 'error'),
  }
}
