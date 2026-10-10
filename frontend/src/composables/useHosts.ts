import { ref } from 'vue'
import { api, type HostsState } from '../api'

// The other machines, as this machine's own app knows them: whether each answers.
const state = ref<HostsState | null>(null)
let loading: Promise<void> | null = null

/** Asked once; the page that follows shows what there is. A machine's coming and going shows in
 * `refresh`. */
export function loadHosts(): Promise<void> {
  loading ??= refresh()
  return loading
}

export async function refresh(): Promise<void> {
  state.value = await api.hosts()
}

export function useHosts() {
  return { state, loadHosts, refresh }
}
