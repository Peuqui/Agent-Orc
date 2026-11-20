import { onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../api'
import type { GpuOrcHolds } from '../gpuHolds'

const REFRESH_MILLISECONDS = 10_000

/** The holds of the GPU-Orcs the backends name, from this machine's own app; one entry per
 * GPU-Orc that holds something (or could not be asked). Kept fresh while the calling component
 * is shown, and only while the page is visible. */
export function useGpuHolds(onError: (error: unknown) => void) {
  const entries = ref<GpuOrcHolds[]>([])

  async function refresh(): Promise<void> {
    try {
      entries.value = await api.gpuOrcHolds()
    } catch (error) {
      onError(error)
    }
  }

  function refreshWhenShown(): void {
    if (document.visibilityState === 'visible') void refresh()
  }

  let timer: number | undefined
  onMounted(() => {
    void refresh()
    timer = window.setInterval(refreshWhenShown, REFRESH_MILLISECONDS)
    document.addEventListener('visibilitychange', refreshWhenShown)
  })
  onBeforeUnmount(() => {
    window.clearInterval(timer)
    document.removeEventListener('visibilitychange', refreshWhenShown)
  })

  return { entries, refresh }
}
