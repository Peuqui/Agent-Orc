import { currentHost, hostPrefix, rootAddress } from '../api'
import { useServerEvents } from './useServerEvents'

/** Calls `onChange` whenever the open permission requests changed on `host` (null: this machine's own;
 * the machine whose page this is without it), and when the stream connects. */
export function useApprovalChanges(onChange: () => void, host: string | null = currentHost): void {
  useServerEvents(new URL(`${hostPrefix(host)}api/approvals/events`, rootAddress()).href, onChange)
}
