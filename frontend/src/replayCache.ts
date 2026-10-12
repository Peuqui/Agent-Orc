// What a TTS service made of a text, kept in memory so that reading the same text again plays it
// without asking the service. The oldest entry goes when the limit is reached; a reload of the page
// empties it.

export class ReplayCache<T> {
  // A Map keeps the order in which keys were added: the first one is the least recently used.
  private readonly entries = new Map<string, T>()

  private readonly limit: number

  constructor(limit: number) {
    this.limit = limit
  }

  get(key: string): T | undefined {
    const found = this.entries.get(key)
    if (found !== undefined) {
      this.entries.delete(key)
      this.entries.set(key, found)
    }
    return found
  }

  set(key: string, value: T): void {
    this.entries.delete(key)
    this.entries.set(key, value)
    const oldest = this.entries.keys().next()
    if (this.entries.size > this.limit && !oldest.done) this.entries.delete(oldest.value)
  }

  clear(): void {
    this.entries.clear()
  }
}
