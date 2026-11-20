import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../api'
import { type GpuHold, type GpuOrcHolds, isFolded, setFolded } from '../gpuHolds'
import { useToast } from './useToast'

const REFRESH_MILLISECONDS = 10_000

// One state per page, shared by the banner and the chips in the headers, so they show the same
// holds and a tap on a chip opens the banner at once.
const entries = ref<GpuOrcHolds[]>([])
// The folded state lives in the storage, which is not reactive: bump this after a change.
const foldedVersion = ref(0)

const held = computed(() =>
  entries.value.flatMap((entry) =>
    entry.hold === null ? [] : [{ address: entry.url ?? entry.backend, entry, hold: entry.hold }],
  ),
)

const toast = useToast()

async function refresh(): Promise<void> {
  try {
    entries.value = await api.gpuOrcHolds()
  } catch (error) {
    toast.error(error)
  }
}

function refreshWhenShown(): void {
  if (document.visibilityState === 'visible') void refresh()
}

function folded(address: string, hold: GpuHold): boolean {
  return foldedVersion.value >= 0 && isFolded(address, hold)
}

function fold(address: string, hold: GpuHold, value: boolean): void {
  setFolded(address, hold, value)
  foldedVersion.value++
}

// Embedded views (the workspace's columns) show nothing and ask nothing: the outermost page does.
const embedded = window.self !== window.top

let consumers = 0
let timer: number | undefined

/** The holds of the GPU-Orcs the backends name, from this machine's own app; one entry per
 * GPU-Orc that holds something (or could not be asked). Polled once per page, only while the page
 * is visible, as long as at least one component uses it. */
export function useGpuHolds() {
  onMounted(() => {
    if (embedded) return
    if (consumers++ > 0) return
    void refresh()
    timer = window.setInterval(refreshWhenShown, REFRESH_MILLISECONDS)
    document.addEventListener('visibilitychange', refreshWhenShown)
  })
  onBeforeUnmount(() => {
    if (embedded) return
    if (--consumers > 0) return
    window.clearInterval(timer)
    document.removeEventListener('visibilitychange', refreshWhenShown)
  })
  return { held, refresh, folded, fold }
}
