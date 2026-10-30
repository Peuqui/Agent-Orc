import { reactive } from 'vue'

// By machine (null: this one's own), since each machine names its agents itself.
const shown = reactive(new Map<string | null, string[]>())

/**
 * The agents that are in view at the moment (the columns of the open workspace, the cards of the
 * agents page): they show their own requests, so the announcement at the top leaves them out. Set
 * by the page that shows them.
 */
export function setShownAgents(host: string | null, ids: string[]): void {
  shown.set(host, ids)
}

export function isShownAgent(host: string | null, id: string): boolean {
  return shown.get(host)?.includes(id) ?? false
}
