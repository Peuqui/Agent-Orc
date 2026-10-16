import type { PeerMessage } from './api'

// A message to every peer online; it forms a conversation of its sender with everyone.
export const EVERYONE = '*'
// The bridge names a person this way (User:Peuqui); peers are Host:Project.
const USER_PREFIX = 'User:'

/** The messages between two (a sorted pair), or of one sender to everyone. */
export interface Conversation {
  key: string
  members: [string, string]
  /** Oldest first. */
  messages: PeerMessage[]
  last: string
}

export function conversationMembers(message: PeerMessage): [string, string] {
  if (message.to === EVERYONE) return [message.from, EVERYONE]
  return [message.from, message.to].sort() as [string, string]
}

/** Conversations with the latest activity first. */
export function groupConversations(messages: Iterable<PeerMessage>): Conversation[] {
  const conversations = new Map<string, Conversation>()
  const chronological = [...messages].sort((a, b) => a.timestamp.localeCompare(b.timestamp))
  for (const message of chronological) {
    const members = conversationMembers(message)
    const key = members.join('\n')
    const conversation = conversations.get(key) ?? { key, members, messages: [], last: '' }
    conversation.messages.push(message)
    conversation.last = message.timestamp
    conversations.set(key, conversation)
  }
  return [...conversations.values()].sort((a, b) => b.last.localeCompare(a.last))
}

/** Who to answer in a conversation: everyone in it but the user, or everyone for a broadcast;
 * nobody where a machine takes part (the bridge's notices), as nothing reaches it. */
export function replyRecipients(conversation: Conversation): string[] {
  if (conversation.members[1] === EVERYONE) return [EVERYONE]
  if (conversation.members.some(isMachine)) return []
  return conversation.members.filter((member) => !member.startsWith(USER_PREFIX))
}

/** Everyone who wrote or was written to, a lane each, in the order they first appear. */
export function lanesOf(messages: Iterable<PeerMessage>): string[] {
  const lanes = new Set<string>()
  const chronological = [...messages].sort((a, b) => a.timestamp.localeCompare(b.timestamp))
  for (const message of chronological) {
    lanes.add(message.from)
    if (message.to !== EVERYONE) lanes.add(message.to)
  }
  return [...lanes]
}

// Peers are Host:Project; a name that is only a host is a machine's own connection to the bridge.
const SEPARATOR = ':'

/** A lane's name without the host (Host:Project, User:Name), so many fit side by side. */
export function laneLabel(name: string): string {
  const separator = name.indexOf(SEPARATOR)
  return separator === -1 ? name : name.slice(separator + 1)
}

/** A machine itself (e.g. "Mini"), no agent: nobody writes to it, so it is not offered. */
export function isMachine(name: string): boolean {
  return !name.includes(SEPARATOR)
}

/** A message with the ones repeating it right after it (same sender, receiver and text), such as
 * a notice the bridge sends again and again; `first` and `last` span their times. */
export interface MessageRun {
  message: PeerMessage
  count: number
  first: string
  last: string
}

/** Runs of repeated messages, in the order given. */
export function collapseRepeats(messages: Iterable<PeerMessage>): MessageRun[] {
  const runs: MessageRun[] = []
  for (const message of messages) {
    const previous = runs.at(-1)?.message
    const repeats =
      previous && previous.from === message.from && previous.to === message.to && previous.content === message.content
    if (!repeats) {
      runs.push({ message, count: 1, first: message.timestamp, last: message.timestamp })
      continue
    }
    const run = runs.at(-1)!
    run.count += 1
    if (message.timestamp < run.first) run.first = message.timestamp
    if (message.timestamp > run.last) run.last = message.timestamp
  }
  return runs
}

/** The runs of one day (local time), in the order given. */
export interface Day {
  key: string
  date: Date
  runs: MessageRun[]
}

export function byDay(runs: Iterable<MessageRun>): Day[] {
  const days: Day[] = []
  for (const run of runs) {
    const date = new Date(run.message.timestamp)
    const key = date.toDateString()
    if (days.at(-1)?.key !== key) days.push({ key, date, runs: [] })
    days.at(-1)!.runs.push(run)
  }
  return days
}

/** Where a message stands in a chat: the user always on the right, as in a messenger; of two
 * agents the one who began on the left; the notices of a machine (the bridge) in the middle. */
export type Side = 'left' | 'right' | 'center'

export function sideOf(conversation: Conversation, sender: string): Side {
  if (isMachine(sender)) return 'center'
  if (sender.startsWith(USER_PREFIX)) return 'right'
  if (conversation.members.some((member) => member.startsWith(USER_PREFIX))) return 'left'
  const starter = conversation.messages.find((message) => !isMachine(message.from))?.from
  return sender === starter ? 'left' : 'right'
}

/** A conversation as a chat: by day, repeats collapsed, the sender's name only where it changes. */
export interface ChatEntry {
  run: MessageRun
  side: Side
  showName: boolean
}

export function chatOf(conversation: Conversation): { key: string; date: Date; entries: ChatEntry[] }[] {
  return byDay(collapseRepeats(conversation.messages)).map((day) => ({
    key: day.key,
    date: day.date,
    entries: day.runs.map((run, index) => ({
      run,
      side: sideOf(conversation, run.message.from),
      showName: index === 0 || day.runs[index - 1]!.message.from !== run.message.from,
    })),
  }))
}

/** A text cut to `maxChars` and `maxLines`; "…" marks that more follows. */
export function clip(text: string, maxChars: number, maxLines: number): string {
  const trimmed = text.trim()
  const lines = trimmed.split('\n')
  let shown = lines.slice(0, maxLines).join('\n')
  if (shown.length > maxChars) shown = shown.slice(0, maxChars).trimEnd()
  return shown.length < trimmed.length ? `${shown}…` : trimmed
}

/** Where a message's arrow runs, in lanes: from the sender to the receiver, or across all lanes
 * for a broadcast (`to` null). */
export function arrowOf(message: PeerMessage, lanes: string[]): { from: number; to: number | null } {
  const from = lanes.indexOf(message.from)
  return { from, to: message.to === EVERYONE ? null : lanes.indexOf(message.to) }
}
