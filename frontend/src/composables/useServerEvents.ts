import { onBeforeUnmount } from 'vue'

interface SharedStream {
  source: EventSource
  listeners: Set<() => void>
}

// One stream per address, however many components listen to it: over HTTP/1.1 a browser keeps
// only about six connections to an address open, and every stream holds one for good, so a stream
// per component starves the page's own requests (and those of every other tab on that address).
const streams = new Map<string, SharedStream>()

function openStream(url: string): SharedStream {
  const source = new EventSource(url)
  const listeners = new Set<() => void>()
  const notify = (): void => listeners.forEach((listener) => listener())
  source.onopen = notify
  source.onmessage = notify
  const stream = { source, listeners }
  streams.set(url, stream)
  return stream
}

/**
 * Calls `onChange` whenever the server reports a change on the stream at `path` (server-sent
 * events, e.g. a workspace or notebook changed on any device), and once the stream (re)connects,
 * so nothing missed while it was down stays missed.
 */
export function useServerEvents(path: string, onChange: () => void): void {
  const url = new URL(path, document.baseURI).href
  const existing = streams.get(url)
  const stream = existing ?? openStream(url)
  // A stream that is already connected will not announce itself again to a late listener.
  if (existing?.source.readyState === EventSource.OPEN) onChange()
  stream.listeners.add(onChange)
  onBeforeUnmount(() => {
    stream.listeners.delete(onChange)
    if (stream.listeners.size === 0) {
      stream.source.close()
      streams.delete(url)
    }
  })
}
