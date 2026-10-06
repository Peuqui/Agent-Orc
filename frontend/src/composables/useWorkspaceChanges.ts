import { useServerEvents } from './useServerEvents'

/** Calls `onChange` whenever a workspace changed on any device, and when the stream connects. */
export function useWorkspaceChanges(onChange: () => void): void {
  useServerEvents('api/workspaces/events', onChange)
}
