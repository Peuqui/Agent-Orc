import { currentHost, hostPrefix, rootAddress } from '../api'
import { useServerEvents } from './useServerEvents'

/** Calls `onChange` whenever a workspace changed on any device (of the app of `host`, null: this
 * machine's own; of the machine whose page this is without it), and when the stream connects. */
export function useWorkspaceChanges(onChange: () => void, host: string | null = currentHost): void {
  useServerEvents(new URL(`${hostPrefix(host)}api/workspaces/events`, rootAddress()).href, onChange)
}
