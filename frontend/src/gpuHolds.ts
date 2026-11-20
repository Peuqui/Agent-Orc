/** A hold of a GPU-Orc (somebody keeps a machine's graphics cards) as the banner shows it. */
export interface GpuHold {
  owner: string
  reason: string
  model: string | null
  /** "requested": a main model is still loaded, nothing is cleared yet; "active": cleared. */
  state: 'requested' | 'active'
  /** Who handed the requested hold the cards by hand; null if nobody did. */
  granted_by: string | null
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
  /** Key of the text that says the state, `{by}` is the one who handed the cards over. */
  stateKey: string
  /** The person may hand the cards over: only a requested hold nobody has handed over yet. */
  canGrant: boolean
  /** Why the button is grayed out, as a key; null while it can be pressed. */
  blockedKey: string | null
  /** Key of the short state word in the folded chip. */
  shortKey: string
  /** A decision is still open (requested, nobody handed over): the folded chip's dot pulses. */
  pulses: boolean
}

export function holdView(hold: GpuHold): HoldView {
  if (hold.state === 'active') {
    return { stateKey: 'gpuHold.state.active', canGrant: false, blockedKey: 'gpuHold.blocked.active', shortKey: 'gpuHold.short.active', pulses: false }
  }
  if (hold.granted_by !== null) {
    return { stateKey: 'gpuHold.state.granted', canGrant: false, blockedKey: 'gpuHold.blocked.granted', shortKey: 'gpuHold.short.granted', pulses: false }
  }
  return { stateKey: 'gpuHold.state.requested', canGrant: true, blockedKey: null, shortKey: 'gpuHold.short.requested', pulses: true }
}

/** What makes a hold the same one again: a new hold of the same owner has a new start. */
export function holdIdentity(hold: GpuHold): string {
  return `${hold.owner}|${hold.since}`
}

const FOLDED_KEY_PREFIX = 'gpuHoldFolded:'

/** Whether this browser folded this hold into the small notice. Storage that cannot be used
 * (private window, blocked site data) is nothing folded. */
export function isFolded(address: string, hold: GpuHold, storage: Pick<Storage, 'getItem'> = localStorage): boolean {
  try {
    return storage.getItem(FOLDED_KEY_PREFIX + address) === holdIdentity(hold)
  } catch {
    return false
  }
}

/** Folds the hold (or opens it again) for this browser only. A storage that cannot be written
 * leaves the banner as it is. */
export function setFolded(
  address: string,
  hold: GpuHold,
  folded: boolean,
  storage: Pick<Storage, 'setItem' | 'removeItem'> = localStorage,
): void {
  try {
    if (folded) storage.setItem(FOLDED_KEY_PREFIX + address, holdIdentity(hold))
    else storage.removeItem(FOLDED_KEY_PREFIX + address)
  } catch {
    // Not saved: the banner shows as before.
  }
}
