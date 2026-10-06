import { onBeforeUnmount } from 'vue'

/**
 * Calls `onChange` whenever the server reports a change on the stream at `path` (server-sent
 * events, e.g. a workspace or notebook changed on any device), and once the stream (re)connects,
 * so nothing missed while it was down stays missed.
 */
export function useServerEvents(path: string, onChange: () => void): void {
  const source = new EventSource(new URL(path, document.baseURI))
  source.onopen = onChange
  source.onmessage = onChange
  onBeforeUnmount(() => source.close())
}
