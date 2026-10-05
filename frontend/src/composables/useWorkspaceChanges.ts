import { onBeforeUnmount } from 'vue'

/**
 * Calls `onChange` whenever a workspace changed on any device (server-sent events), and once
 * the stream (re)connects, so nothing missed while it was down stays missed.
 */
export function useWorkspaceChanges(onChange: () => void): void {
  const source = new EventSource(new URL('api/workspaces/events', document.baseURI))
  source.onopen = onChange
  source.onmessage = onChange
  onBeforeUnmount(() => source.close())
}
