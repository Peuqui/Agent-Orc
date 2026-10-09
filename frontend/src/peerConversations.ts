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

/** The first line of a text, cut to `maxChars`; "…" marks that more follows. */
export function firstLine(text: string, maxChars: number): string {
  const trimmed = text.trim()
  const line = trimmed.split('\n', 1)[0]!
  if (line.length > maxChars) return `${line.slice(0, maxChars).trimEnd()}…`
  return line.length < trimmed.length ? `${line}…` : line
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

/** Where a message's arrow runs, in lanes: from the sender to the receiver, or across all lanes
 * for a broadcast (`to` null). */
export function arrowOf(message: PeerMessage, lanes: string[]): { from: number; to: number | null } {
  const from = lanes.indexOf(message.from)
  return { from, to: message.to === EVERYONE ? null : lanes.indexOf(message.to) }
}
