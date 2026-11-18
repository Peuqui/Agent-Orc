import type { HostStatus } from './api'

export type PowerAction = 'suspend' | 'poweroff'

/** What a machine's own config lets this one do to it (GET /api/power of that machine). */
export type PowerPermissions = Record<PowerAction, boolean>

export const POWER_ACTIONS: PowerAction[] = ['suspend', 'poweroff']

/** How long a machine is given to go away after the command; then the button is back. */
export const POWER_PATIENCE_MS = 3 * 60 * 1000

/** The buttons of a machine's card: for another machine that answers and allows the action itself.
 * Never for this machine's own card (`host` null): it would switch off the machine serving the page. */
export function powerButtons(
  machine: { state: HostStatus; host: string | null },
  permissions: PowerPermissions | undefined,
): PowerAction[] {
  if (machine.host === null || machine.state !== 'online' || permissions === undefined) return []
  return POWER_ACTIONS.filter((action) => permissions[action])
}
