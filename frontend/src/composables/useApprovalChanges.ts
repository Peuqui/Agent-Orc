import { hostPrefix } from '../api'
import { useServerEvents } from './useServerEvents'

/** Calls `onChange` whenever the open permission requests changed on this machine (or on `host`),
 * and when the stream connects. */
export function useApprovalChanges(onChange: () => void, host: string | null = null): void {
  useServerEvents(`${hostPrefix(host)}api/approvals/events`, onChange)
}
