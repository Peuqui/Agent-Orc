import { computed, ref } from 'vue'
import { api, type ScopeState } from '../api'

const TICK_MILLISECONDS = 1000
const MILLISECONDS_PER_SECOND = 1000

const scope = ref<ScopeState | null>(null)
// Wall-clock end of the unlock, so the countdown stays right while the app sleeps.
const unlockedUntil = ref(0)
const now = ref(Date.now())
let ticker: number | undefined

function apply(state: ScopeState): void {
  scope.value = state
  // Both from the same instant; a stale `now` would show a phantom countdown.
  now.value = Date.now()
  unlockedUntil.value = now.value + state.seconds_unlocked * MILLISECONDS_PER_SECOND
  window.clearInterval(ticker)
  if (state.seconds_unlocked > 0) {
    ticker = window.setInterval(() => {
      now.value = Date.now()
      if (now.value >= unlockedUntil.value) void load()
    }, TICK_MILLISECONDS)
  }
}

async function load(): Promise<void> {
  apply(await api.scope())
}

const secondsLeft = computed(() =>
  Math.max(0, (unlockedUntil.value - now.value) / MILLISECONDS_PER_SECOND),
)

export function useScope() {
  return {
    scope,
    secondsLeft,
    load,
    unlock: async (password: string) => apply(await api.unlock(password)),
    lock: async () => apply(await api.lock()),
  }
}
