import { ref } from 'vue'

// One clock for everything that counts down on the page (cache markers): ticking every half
// minute is fine enough for minutes, and one timer serves them all.
const TICK_MILLISECONDS = 30_000
const MILLISECONDS_PER_SECOND = 1000

const now = ref(Date.now() / MILLISECONDS_PER_SECOND)
let ticker: number | undefined

/** The current time in Unix seconds, updated every half minute. */
export function useNow() {
  ticker ??= window.setInterval(() => (now.value = Date.now() / MILLISECONDS_PER_SECOND), TICK_MILLISECONDS)
  return now
}
