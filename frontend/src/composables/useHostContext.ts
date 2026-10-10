import { getCurrentInstance, inject, provide, type InjectionKey } from 'vue'
import { apiFor } from '../api'

// The machine whose agents a component shows: set by the one that lists them, read by everything
// below it, so a card's buttons need not know whose card they are on.
const HOST_KEY: InjectionKey<string | null> = Symbol('host')

export function provideHost(host: string | null): void {
  provide(HOST_KEY, host)
}

/** The machine of the component's surroundings; null (this machine's own) where none is set or
 * outside a component. */
export function useHostContext(): string | null {
  return getCurrentInstance() === null ? null : inject(HOST_KEY, null)
}

/** The calls to the app of that machine. */
export function useApi(): ReturnType<typeof apiFor> {
  return apiFor(useHostContext())
}
