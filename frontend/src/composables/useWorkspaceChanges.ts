import { hostPrefix } from '../api'
import { useServerEvents } from './useServerEvents'

/** Calls `onChange` whenever a workspace changed on any device (of this machine's own app, or of
 * `host`'s), and when the stream connects. */
export function useWorkspaceChanges(onChange: () => void, host: string | null = null): void {
  useServerEvents(`${hostPrefix(host)}api/workspaces/events`, onChange)
}
