// A request in the banner at the top of the page can be folded to a pill in the header, like a hold
// (gpuHolds.ts). Folded is a request id, not an agent: a new request of the same agent shows open again.

/** Whether an agent's waiting requests show as a pill: every one of them was folded. */
export function agentFolded(approvalIds: readonly string[], folded: ReadonlySet<string>): boolean {
  return approvalIds.length > 0 && approvalIds.every((id) => folded.has(id))
}
