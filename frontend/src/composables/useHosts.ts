import { onBeforeUnmount, onMounted, ref } from 'vue'
import { api, type HostsState } from '../api'

// The other machines, as this machine's own app knows them: whether each answers.
const state = ref<HostsState | null>(null)
const REFRESH_MILLISECONDS = 3000
let loading: Promise<void> | null = null
let watchers = 0
let timer: number | undefined

/** Asked once; the page that follows shows what there is. A machine's coming and going shows in
 * `refresh`. */
export function loadHosts(): Promise<void> {
  loading ??= refresh()
  return loading
}

export async function refresh(): Promise<void> {
  state.value = await api.hosts()
}

/** Keeps the state fresh while the calling component is shown: one timer however many ask, and a
 * machine's coming and going shows within a few seconds. */
function keepFresh(): void {
  onMounted(() => {
    watchers += 1
    if (watchers === 1) {
      timer = window.setInterval(() => {
        if (document.visibilityState === 'visible') refresh().catch(() => undefined)
      }, REFRESH_MILLISECONDS)
    }
  })
  onBeforeUnmount(() => {
    watchers -= 1
    if (watchers === 0) window.clearInterval(timer)
  })
}

export function useHosts() {
  return { state, loadHosts, refresh, keepFresh }
}
