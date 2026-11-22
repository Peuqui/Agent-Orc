/** A hold of a GPU-Orc (somebody keeps a machine's graphics cards) as the banner shows it. */
export interface GpuHold {
  owner: string
  reason: string
  model: string | null
  /** "requested": a main model is still loaded, nothing is cleared yet; "active": cleared. */
  state: 'requested' | 'active'
  /** Who handed the requested hold the cards by hand; null if nobody did. */
  granted_by: string | null
  /** Who asked the owner of the active hold to end it; null if nobody did. */
  end_requested_by: string | null
  since: string
}

/** One GPU-Orc named by the backends: its hold, or why it could not be asked. */
export interface GpuOrcHolds {
  backend: string
  label: string
  url: string | null
  hold: GpuHold | null
  error: string | null
}

export interface HoldView {
  /** Key of the text that says the state; `{by}` is `by`, `{owner}` the hold's owner. */
  stateKey: string
  /** Who handed the cards over or asked for the end, for the state text; null if nobody. */
  by: string | null
  /** The person may hand the cards over: only a requested hold nobody has handed over yet. */
  canGrant: boolean
  /** Why the button is grayed out, as a key; null while it can be pressed. */
  blockedKey: string | null
  /** Key of the short state word in the folded chip. */
  shortKey: string
  /** A decision is still open (requested, nobody handed over): the banner opens by itself and the
   * folded chip's dot pulses. Otherwise the hold shows as the chip until a tap opens it. */
  decisionOpen: boolean
  /** Somebody asked the owner of the active hold to end it: asking again does nothing, and letting
   * go at once is for an owner that does not react to that request. */
  endAsked: boolean
}

export function holdView(hold: GpuHold): HoldView {
  if (hold.state === 'active' && hold.end_requested_by !== null) {
    return { stateKey: 'gpuHold.state.ending', by: hold.end_requested_by, canGrant: false, blockedKey: 'gpuHold.blocked.active', shortKey: 'gpuHold.short.ending', decisionOpen: false, endAsked: true }
  }
  if (hold.state === 'active') {
    return { stateKey: 'gpuHold.state.active', by: null, canGrant: false, blockedKey: 'gpuHold.blocked.active', shortKey: 'gpuHold.short.active', decisionOpen: false, endAsked: false }
  }
  if (hold.granted_by !== null) {
    return { stateKey: 'gpuHold.state.granted', by: hold.granted_by, canGrant: false, blockedKey: 'gpuHold.blocked.granted', shortKey: 'gpuHold.short.granted', decisionOpen: false, endAsked: false }
  }
  return { stateKey: 'gpuHold.state.requested', by: null, canGrant: true, blockedKey: null, shortKey: 'gpuHold.short.requested', decisionOpen: true, endAsked: false }
}

/** What makes a hold the same one again: a new hold of the same owner has a new start. */
export function holdIdentity(hold: GpuHold): string {
  return `${hold.owner}|${hold.since}`
}

const FOLDED_KEY_PREFIX = 'gpuHoldFolded:'

/** Whether this browser shows this hold as the small chip: as the person last chose for this
 * hold ("Later" or a tap on the chip), otherwise folded unless a decision is open. Storage that
 * cannot be used (private window, blocked site data) counts as no choice. */
export function isFolded(address: string, hold: GpuHold, storage: Pick<Storage, 'getItem'> = localStorage): boolean {
  let stored: string | null = null
  try {
    stored = storage.getItem(FOLDED_KEY_PREFIX + address)
  } catch {
    // No choice readable: the state decides.
  }
  if (stored === `${holdIdentity(hold)}|folded`) return true
  if (stored === `${holdIdentity(hold)}|open`) return false
  return !holdView(hold).decisionOpen
}

/** Folds the hold (or opens it again) for this browser only. A storage that cannot be written
 * leaves the hold as its state shows it. */
export function setFolded(
  address: string,
  hold: GpuHold,
  folded: boolean,
  storage: Pick<Storage, 'setItem'> = localStorage,
): void {
  try {
    storage.setItem(FOLDED_KEY_PREFIX + address, `${holdIdentity(hold)}|${folded ? 'folded' : 'open'}`)
  } catch {
    // Not saved: the hold shows as its state says.
  }
}
