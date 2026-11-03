/** `load` run once for every caller: a load that went through is not repeated, while one in progress
 * is shared. A load that failed is not kept, so the next call tries again instead of being handed
 * the old failure (one network gap at the start would otherwise fail every later caller at once). */
export function loadOnce(load: () => Promise<void>): () => Promise<void> {
  let loading: Promise<void> | null = null
  return () => {
    loading ??= load().catch((error: unknown) => {
      loading = null
      throw error
    })
    return loading
  }
}
