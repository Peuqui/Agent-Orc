import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createServiceHost, type DictationServiceState } from '../src/dictationService.ts'

function stateWith(gpuLoaded: boolean, ttl: number | null = null): DictationServiceState {
  return {
    language: 'de',
    stt: true,
    service: { gpu: 'parakeet', cpu: 'parakeet', gpu_loaded: gpuLoaded, cpu_loaded: true, gpu_ttl_remaining_seconds: ttl },
  }
}

// A page as the host sees it: only whether it was closed (a removed column's iframe).
function page(): Window & { closed: boolean } {
  return { closed: false } as Window & { closed: boolean }
}

function failOnError(error: unknown): void {
  throw error
}

test('a dictation in one column shows the GPU on the buttons of every column', async () => {
  let answer = stateWith(false)
  const host = createServiceHost(async () => answer, failOnError)
  const left: boolean[] = []
  const right: boolean[] = []
  host.watch(page(), (state) => left.push(state.service?.gpu_loaded ?? false))
  host.watch(page(), (state) => right.push(state.service?.gpu_loaded ?? false))
  await host.refresh()
  // The right column's dictation loaded the GPU model and asks the service again.
  answer = stateWith(true)
  await host.refresh()
  assert.deepEqual(left, [false, true])
  assert.deepEqual(right, [false, true])
})

test('a column opened later sees the state known so far at once', async () => {
  const host = createServiceHost(async () => stateWith(true), failOnError)
  await host.refresh()
  const seen: boolean[] = []
  host.watch(page(), (state) => seen.push(state.service?.gpu_loaded ?? false))
  assert.deepEqual(seen, [true])
})

test('a removed column is not told any more, nor one that stopped watching', async () => {
  const host = createServiceHost(async () => stateWith(true), failOnError)
  const removed = page()
  let removedTold = 0
  let stoppedTold = 0
  host.watch(removed, () => removedTold++)
  const stop = host.watch(page(), () => stoppedTold++)
  removed.closed = true
  stop()
  await host.refresh()
  assert.equal(removedTold, 0)
  assert.equal(stoppedTold, 0)
})

test('one timer asks again when the idle GPU worker has ended, and every column hears it', async (context) => {
  context.mock.timers.enable({ apis: ['setTimeout'] })
  let asked = 0
  let answer = stateWith(true, 60)
  const host = createServiceHost(async () => {
    asked++
    return answer
  }, failOnError)
  const left: boolean[] = []
  const right: boolean[] = []
  host.watch(page(), (state) => left.push(state.service?.gpu_loaded ?? false))
  host.watch(page(), (state) => right.push(state.service?.gpu_loaded ?? false))
  // Both columns open and ask: still one timer, not one per field.
  await host.refresh()
  await host.refresh()
  assert.equal(asked, 2)
  answer = stateWith(false)
  context.mock.timers.tick(61_000)
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(asked, 3)
  assert.deepEqual(left, [true, true, false])
  assert.deepEqual(right, [true, true, false])
})

test('an error of the service goes to the error display, nobody is told a state', async () => {
  const errors: unknown[] = []
  const host = createServiceHost(async () => {
    throw new Error('down')
  }, (error) => errors.push(error))
  let told = 0
  host.watch(page(), () => told++)
  await host.refresh()
  assert.equal(errors.length, 1)
  assert.equal(told, 0)
})
