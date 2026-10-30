import { ref } from 'vue'
import { api, type HostsState } from '../api'
import { useServerEvents } from './useServerEvents'

// The other machines, as this machine's own app knows them: whether each answers.
const state = ref<HostsState | null>(null)
let loading: Promise<void> | null = null
let refreshing: Promise<void> | null = null

/** Asked once; the page that follows shows what there is. A machine's coming and going shows in
 * `keepFresh`. */
export function loadHosts(): Promise<void> {
  loading ??= refresh()
  return loading
}

/** One request however many components ask at once (each listener of the stream asks). */
export function refresh(): Promise<void> {
  refreshing ??= api.hosts().then((hosts) => {
    state.value = hosts
  }).finally(() => {
    refreshing = null
  })
  return refreshing
}

/** Keeps the state fresh while the calling component is shown: the server reports a machine's
 * coming and going. */
function keepFresh(): void {
  useServerEvents('api/hosts/events', () => void refresh().catch(() => undefined))
}

export function useHosts() {
  return { state, loadHosts, refresh, keepFresh }
}
