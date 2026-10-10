import assert from 'node:assert/strict'
import test from 'node:test'

class FakeEventSource {
  static readonly OPEN = 1
  static created: FakeEventSource[] = []
  readyState = 0
  onopen: (() => void) | null = null
  onmessage: (() => void) | null = null
  readonly url: string
  constructor(url: string) {
    this.url = url
    FakeEventSource.created.push(this)
  }
  close(): void {}
}

// Vue is loaded first: it takes a global `document` for a browser and wants a real one.
const { useServerEvents } = await import('../src/composables/useServerEvents.ts')
Object.assign(globalThis, {
  EventSource: FakeEventSource,
  document: { baseURI: 'https://example.test/agent-orc/' },
})

// The unmount hook needs a component; Vue says so for each call here, which is of no interest.
const warn = console.warn
console.warn = (message?: unknown, ...rest: unknown[]): void => {
  if (typeof message !== 'string' || !message.includes('onBeforeUnmount')) warn(message, ...rest)
}

test('listeners of one address share a single stream', () => {
  const calls: string[] = []
  useServerEvents('api/workspaces/events', () => calls.push('first'))
  useServerEvents('api/workspaces/events', () => calls.push('second'))
  assert.equal(FakeEventSource.created.length, 1)
  FakeEventSource.created[0]!.onmessage?.()
  assert.deepEqual(calls, ['first', 'second'])
})

test('another address gets a stream of its own', () => {
  useServerEvents('hosts/Aragon/api/workspaces/events', () => {})
  assert.equal(FakeEventSource.created.length, 2)
})

test('a listener added to a connected stream is told at once', () => {
  FakeEventSource.created[0]!.readyState = FakeEventSource.OPEN
  const calls: string[] = []
  useServerEvents('api/workspaces/events', () => calls.push('late'))
  assert.deepEqual(calls, ['late'])
  assert.equal(FakeEventSource.created.length, 2)
})
