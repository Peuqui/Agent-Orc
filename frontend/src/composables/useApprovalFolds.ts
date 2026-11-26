import { computed, reactive } from 'vue'
import { agentFolded } from '../approvalFolds'

/** An agent whose requests wait in the banner, as the pills need it. */
export interface WaitingAgent {
  key: string
  name: string
  hostName: string | null
  approvalIds: string[]
}

// One state per page, shared by the banner (HostApprovals, one per machine) and the pills in the
// headers (BannerChips). Only in memory: a reload shows the waiting requests open again. Embedded
// views (the workspace's columns) have their own, empty state: the outermost page shows the banner.
const folded = reactive(new Set<string>())
const waitingByHost = reactive(new Map<string, WaitingAgent[]>())

const foldedAgents = computed(() =>
  [...waitingByHost.values()].flat().filter((agent) => agentFolded(agent.approvalIds, folded)),
)

function isFolded(approvalIds: readonly string[]): boolean {
  return agentFolded(approvalIds, folded)
}

function fold(approvalIds: readonly string[], value: boolean): void {
  for (const id of approvalIds) {
    if (value) folded.add(id)
    else folded.delete(id)
  }
}

/** The banner of one machine names the agents waiting there (host: '' for this machine). */
function publish(host: string, agents: WaitingAgent[]): void {
  waitingByHost.set(host, agents)
}

function withdraw(host: string): void {
  waitingByHost.delete(host)
}

export function useApprovalFolds() {
  return { foldedAgents, isFolded, fold, publish, withdraw }
}
