import { computed, getCurrentInstance, inject, provide, type ComputedRef, type InjectionKey } from 'vue'
import { apiFor, currentHost } from '../api'
import { useHosts } from './useHosts'
import { useToast } from './useToast'

// The machine whose agents a component shows: set by the one that lists them, read by everything
// below it, so a card's buttons need not know whose card they are on.
const HOST_KEY: InjectionKey<string | null> = Symbol('host')

export function provideHost(host: string | null): void {
  provide(HOST_KEY, host)
}

/** The machine of the component's surroundings (null: this machine's own, the Zentrale); the
 * machine whose page this is where none is set or outside a component. */
export function useHostContext(): string | null {
  return getCurrentInstance() === null ? currentHost : inject(HOST_KEY, currentHost)
}

/** The calls to the app of that machine. */
export function useApi(): ReturnType<typeof apiFor> {
  return apiFor(useHostContext())
}

/** The name of the machine of the component's surroundings, for texts: "this machine" says nothing on a
 * page of Mini opened from Aragon. Null until the machines are known (asked once). */
export function useMachineName(): ComputedRef<string | null> {
  const host = useHostContext()
  const own = useServiceMachineName()
  return computed(() => host ?? own.value)
}

/** The name of the machine whose own app serves the user's services (dictation, reading aloud): they
 * always go there, whichever machine's page is open. Null until the machines are known (asked once). */
export function useServiceMachineName(): ComputedRef<string | null> {
  const { state, loadHosts } = useHosts()
  loadHosts().catch(useToast().error)
  return computed(() => state.value?.self ?? null)
}
