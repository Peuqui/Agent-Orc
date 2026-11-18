import type { HostStatus } from './api'

/** How long a machine is given to come up after its wake-up packet; then the button is back. */
export const WAKE_PATIENCE_MS = 3 * 60 * 1000

/** The button to wake a machine is for one that does not answer and that the config can wake. */
export function offersWake(machine: { state: HostStatus; canWake: boolean }): boolean {
  return machine.state !== 'online' && machine.canWake
}
