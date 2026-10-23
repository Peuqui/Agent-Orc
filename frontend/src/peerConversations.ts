import type { PeerMessage } from './api'

// A message to every peer online; it forms a conversation of its sender with everyone.
export const EVERYONE = '*'
// The bridge names a person this way (User:Peuqui); peers are Host:Project.
const USER_PREFIX = 'User:'

/** The messages between two, or of one sender to everyone. */
export interface Conversation {
  key: string
  /** Who started it first, then who was written to. */
  members: [string, string]
  /** Oldest first. */
  messages: PeerMessage[]
  last: string
}

/** The same for both directions of a pair, so they form one conversation. */
function conversationKey(message: PeerMessage): string {
  const pair = message.to === EVERYONE ? [message.from, EVERYONE] : [message.from, message.to].sort()
  return pair.join('\n')
}

/** Conversations with the latest activity first. */
export function groupConversations(messages: Iterable<PeerMessage>): Conversation[] {
  const conversations = new Map<string, Conversation>()
  const chronological = [...messages].sort((a, b) => a.timestamp.localeCompare(b.timestamp))
  for (const message of chronological) {
    const key = conversationKey(message)
    const conversation = conversations.get(key) ?? { key, members: [message.from, message.to], messages: [], last: '' }
    conversation.messages.push(message)
    conversation.last = message.timestamp
    conversations.set(key, conversation)
  }
  return [...conversations.values()].sort((a, b) => b.last.localeCompare(a.last))
}

/** The conversations in the order of `keys` (the order they had); those not in it (new ones) come
 * first, in their own order. Moving a conversation's element in the page takes the cursor away
 * from a field in it, so the list must not reorder while one is being written in. */
export function keepOrder(conversations: Conversation[], keys: string[]): Conversation[] {
  const place = (conversation: Conversation): number => keys.indexOf(conversation.key)
  return [...conversations].sort((a, b) => place(a) - place(b))
}

/** Who to answer in a conversation: everyone in it but the user, or everyone for a broadcast;
 * nobody where a machine takes part (the bridge's notices), as nothing reaches it. */
export function replyRecipients(conversation: Conversation): string[] {
  if (conversation.members[1] === EVERYONE) return [EVERYONE]
  if (conversation.members.some(isMachine)) return []
  return conversation.members.filter((member) => !member.startsWith(USER_PREFIX))
}

/** Everyone who wrote or was written to, a lane each, in the order they first appear; the
 * machines (the bridge) at the far end, as their notices are the least of it. */
export function lanesOf(messages: Iterable<PeerMessage>): string[] {
  const lanes = new Set<string>()
  const chronological = [...messages].sort((a, b) => a.timestamp.localeCompare(b.timestamp))
  for (const message of chronological) {
    lanes.add(message.from)
    if (message.to !== EVERYONE) lanes.add(message.to)
  }
  return [...lanes].sort((a, b) => Number(isMachine(a)) - Number(isMachine(b)))
}

// A colour for each agent and user, the same in every view: its name, its lane and its arrows.
// None of the state colours (amber, red, emerald), so a name is not taken for a state.
const PEER_COLORS = [
  'text-sky-400',
  'text-violet-400',
  'text-orange-400',
  'text-teal-300',
  'text-pink-400',
  'text-lime-400',
  'text-indigo-300',
  'text-yellow-200',
]
// The machines' notices step back.
export const MACHINE_COLOR = 'text-slate-500'

/** Each lane's colour, by its place among the lanes; more lanes than colours share them. */
export function colorsOf(lanes: string[]): Map<string, string> {
  const colors = new Map<string, string>()
  let next = 0
  for (const lane of lanes) {
    if (isMachine(lane)) colors.set(lane, MACHINE_COLOR)
    else colors.set(lane, PEER_COLORS[next++ % PEER_COLORS.length]!)
  }
  return colors
}

/** Whether a message concerns someone: from them, to them, or to everyone. */
export function involves(message: PeerMessage, name: string): boolean {
  return message.from === name || message.to === name || message.to === EVERYONE
}

// The handshake's tags (see AI-Connect's rules): agreement, or "not done yet".
export const HANDSHAKE_TAGS = ['LGTM', 'CONTINUE'] as const
export type HandshakeTag = (typeof HANDSHAKE_TAGS)[number]
const HANDSHAKE_PATTERN = new RegExp(`\\s*\\[(${HANDSHAKE_TAGS.join('|')})\\]`, 'g')

/** A message's text as it is shown: without the sender's own name in front ("Mini:A: …" or
 * "A: …", which many agents write though their name stands above it) and without the handshake's
 * tags, which it carried to be shown as marks. */
export function readableOf(message: PeerMessage): { text: string; tags: HandshakeTag[] } {
  let text = message.content.trim()
  const prefix = [message.from, laneLabel(message.from)].map((name) => `${name}:`).find((name) => text.startsWith(name))
  if (prefix) text = text.slice(prefix.length)
  const tags = [...text.matchAll(HANDSHAKE_PATTERN)].map((match) => match[1] as HandshakeTag)
  return { text: text.replace(HANDSHAKE_PATTERN, '').trim(), tags: [...new Set(tags)] }
}

/** The messages of a conversation after the last one seen, but the user's own and a machine's
 * notices (the bridge repeats them, they would only drown the rest). */
export function unreadCount(conversation: Conversation, seenId: number): number {
  return conversation.messages.filter(
    (message) => message.id > seenId && !message.from.startsWith(USER_PREFIX) && !isMachine(message.from),
  ).length
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
