<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type Peer, type PeerEvent, type PeerMessage } from '../api'
import PeerComposer from '../components/PeerComposer.vue'
import PeerLanes from '../components/PeerLanes.vue'
import PeerMessageItem from '../components/PeerMessageItem.vue'
import { useHeightVariable } from '../composables/useHeightVariable'
import { useToast } from '../composables/useToast'
import { formatMoment } from '../format'
import { EVERYONE, groupConversations, isMachine, laneLabel, lanesOf, replyRecipients, type Conversation } from '../peerConversations'

// AI-Connect read along: the conversations between the agents, live, and fields to write to
// them as the user: below each open conversation to those in it, at the foot to whom one picks. The server runs AI-Connect's program per open page and hands its lines on;
// when it ends (the bridge restarted, or cannot be reached) the stream ends and the browser
// connects again by itself, getting the history anew. A refused token ends it for good.
const FINAL_ERRORS = new Set(['token_refused', 'token_missing'])

const toast = useToast()
// So a field opened in a conversation stays clear of the foot when it gets the cursor.
useHeightVariable('--peers-foot-height', 'foot')
const { locale, t } = useI18n()

const configured = ref<boolean | null>(null)
const userName = ref('')
const peers = ref<Peer[]>([])
const messages = ref<PeerMessage[]>([])
const known = new Set<number>()
const historyLoaded = ref(false)
const streamError = ref<string | null>(null)
const view = ref<'tree' | 'timeline' | 'lanes'>('tree')
const openConversations = ref(new Set<string>())
// The conversation opened by its "Answer" button, whose field gets the cursor.
const answering = ref<string | null>(null)

// Whom the field at the foot writes to: for a conversation there is none yet, or a broadcast.
const recipients = ref<string[]>([])

let source: EventSource | null = null

api.peers().then((state) => {
  configured.value = state.configured
  userName.value = state.user_name
  if (state.configured) connect()
}, toast.error)

function connect(): void {
  source = new EventSource(new URL('api/peers/events', document.baseURI))
  source.onmessage = (event) => receive(JSON.parse(event.data) as PeerEvent)
}

function receive(event: PeerEvent): void {
  if (event.event === 'peers') {
    peers.value = event.peers
    streamError.value = null
  } else if (event.event === 'message') {
    // After a reconnect the history comes again.
    if (known.has(event.id)) return
    known.add(event.id)
    const { event: _kind, ...message } = event
    messages.value.push(message)
  } else if (event.event === 'history_end') {
    historyLoaded.value = true
  } else {
    streamError.value = event.kind
    if (FINAL_ERRORS.has(event.kind)) source?.close()
  }
}

onBeforeUnmount(() => source?.close())

const conversations = computed(() => groupConversations(messages.value))
const timeline = computed(() => [...messages.value].sort((a, b) => b.timestamp.localeCompare(a.timestamp)))
const sortedPeers = computed(() =>
  peers.value.filter((peer) => !isMachine(peer.name)).sort((a, b) => a.name.localeCompare(b.name)),
)
const peerNames = computed(() => sortedPeers.value.map((peer) => peer.name))
const lanes = computed(() => lanesOf(messages.value))
const laneColumns = computed(() => ({ gridTemplateColumns: `repeat(${lanes.value.length}, minmax(0, 1fr))` }))
const chosenClass = 'border-sky-500 bg-sky-900/40 text-sky-200'

// What a peer does, as AI-Connect's hooks in its session report it.
const STATE_COLORS: Record<string, string> = {
  busy: 'text-amber-400',
  waiting: 'text-red-400',
  idle: 'text-emerald-400',
}

// A peer whose session reports nothing (no AI-Connect hooks).
const NO_STATE_COLOR = 'text-slate-500'

function stateColor(peer: Peer): string {
  return STATE_COLORS[peer.state ?? ''] ?? NO_STATE_COLOR
}

/** The peer's name, what it does in words, and the line it set on what it works on. */
function peerTitle(peer: Peer): string {
  const state = peer.state && peer.state in STATE_COLORS ? t(`peers.state.${peer.state}`) : peer.state
  return [peer.name, state, peer.state_detail, peer.status].filter(Boolean).join(' · ')
}
// Chosen, but gone offline since: still shown, so they can be taken off; they get it when they come back.
const offlineRecipients = computed(() =>
  recipients.value.filter((recipient) => recipient !== EVERYONE && !peerNames.value.includes(recipient)),
)

function title(conversation: Conversation): string {
  const [first, second] = conversation.members
  return second === EVERYONE ? `${first} → ${t('peers.everyone')}` : `${first} ↔ ${second}`
}

function toggleConversation(key: string): void {
  answering.value = null
  const open = new Set(openConversations.value)
  if (!open.delete(key)) open.add(key)
  openConversations.value = open
}

function toggleRecipient(name: string): void {
  if (name === EVERYONE) {
    recipients.value = recipients.value.includes(EVERYONE) ? [] : [EVERYONE]
    return
  }
  const others = recipients.value.filter((recipient) => recipient !== EVERYONE)
  recipients.value = others.includes(name) ? others.filter((other) => other !== name) : [...others, name]
}

function answer(conversation: Conversation): void {
  openConversations.value = new Set(openConversations.value).add(conversation.key)
  answering.value = conversation.key
}

/** "As User:Peuqui to Agent-Orc, AI-Connect …" */
function replyPlaceholder(recipients: string[]): string {
  const names = recipients.map((name) => (name === EVERYONE ? t('peers.everyone') : laneLabel(name)))
  return t('peers.asUserTo', { name: userName.value, names: names.join(', ') })
}
</script>

<template>
  <section class="flex flex-col gap-4">
    <!-- Stays below the app's header while the conversations scroll; in the lanes view it carries
         the lanes' names, so they stay readable over every arrow. -->
    <div class="sticky top-(--app-header-height) z-20 -mx-4 -mt-4 bg-slate-900 px-4 pt-4 pb-1">
      <div class="flex flex-wrap items-center gap-2">
        <h1 class="flex-1 text-lg font-semibold">{{ $t('peers.title') }}</h1>
        <div v-if="configured" class="flex overflow-hidden rounded-md border border-slate-600 text-sm">
          <button
            v-for="mode in ['tree', 'timeline', 'lanes'] as const"
            :key="mode"
            class="px-3 py-1"
            :class="view === mode ? 'bg-slate-600 text-slate-100' : 'text-slate-400 hover:bg-slate-700'"
            @click="view = mode"
          >
            {{ $t(`peers.view.${mode}`) }}
          </button>
        </div>
      </div>
      <div
        v-if="view === 'lanes' && lanes.length"
        class="mt-3 -mb-1 grid gap-1 rounded-t-xl border-x border-t border-slate-700 bg-slate-800 px-3 py-2"
        :style="laneColumns"
      >
        <span v-for="lane in lanes" :key="lane" class="truncate text-center text-xs font-medium text-amber-400" :title="lane">
          {{ laneLabel(lane) }}
        </span>
      </div>
    </div>

    <p v-if="configured === false" class="card p-6 text-center text-slate-400">{{ $t('peers.notConfigured') }}</p>
    <template v-else-if="configured">
      <div v-if="sortedPeers.length" class="flex flex-wrap gap-2 text-xs">
        <span
          v-for="peer in sortedPeers"
          :key="peer.name"
          class="rounded-full border border-slate-600 px-2 py-0.5 text-slate-300"
          :title="peerTitle(peer)"
        >
          <span :class="stateColor(peer)">●</span> {{ peer.name }}
        </span>
      </div>
      <p v-if="sortedPeers.length" class="-mt-2 flex flex-wrap gap-x-3 text-xs text-slate-500">
        <span v-for="(color, state) in STATE_COLORS" :key="state"><span :class="color">●</span> {{ $t(`peers.state.${state}`) }}</span>
        <span><span :class="NO_STATE_COLOR">●</span> {{ $t('peers.state.none') }}</span>
      </p>

      <p v-if="streamError" class="card border-amber-700 p-3 text-sm text-amber-300">
        {{ $t(`peers.streamError.${streamError}`) }}
      </p>

      <p v-if="!historyLoaded && !streamError" class="card p-6 text-center text-slate-400">{{ $t('peers.loading') }}</p>
      <p v-else-if="historyLoaded && !messages.length" class="card p-6 text-center text-slate-400">
        {{ $t('peers.empty') }}
      </p>

      <div v-else-if="view === 'tree'" class="flex flex-col gap-2">
        <div v-for="conversation in conversations" :key="conversation.key" class="card">
          <div class="flex items-center gap-2 p-1.5">
            <button
              type="button"
              class="press-row flex min-w-0 flex-1 flex-col p-1.5 text-left"
              :aria-expanded="openConversations.has(conversation.key)"
              @click="toggleConversation(conversation.key)"
            >
              <span class="text-sm font-medium break-words text-amber-400">{{ title(conversation) }}</span>
              <span class="text-xs text-slate-500">
                {{ $t('peers.count', { count: conversation.messages.length }) }} ·
                {{ formatMoment(new Date(conversation.last), locale) }}
              </span>
            </button>
            <button
              v-if="replyRecipients(conversation).length && !openConversations.has(conversation.key)"
              type="button"
              class="btn-secondary btn-small mr-1.5"
              @click="answer(conversation)"
            >
              {{ $t('peers.answer') }}
            </button>
          </div>
          <div v-if="openConversations.has(conversation.key)" class="border-t border-slate-700 px-3 pb-3">
            <PeerMessageItem v-for="message in conversation.messages" :key="message.id" :message="message" />
            <PeerComposer
              v-if="replyRecipients(conversation).length"
              :recipients="replyRecipients(conversation)"
              :placeholder="replyPlaceholder(replyRecipients(conversation))"
              :focused="answering === conversation.key"
              class="mt-1 [&_textarea]:scroll-mb-[calc(var(--bottom-nav-height)+var(--peers-foot-height))]"
            />
          </div>
        </div>
      </div>

      <div v-else-if="view === 'timeline'" class="card px-3 py-1">
        <PeerMessageItem v-for="message in timeline" :key="message.id" :message="message" />
      </div>

      <PeerLanes v-else :messages="timeline" :lanes="lanes" :columns="laneColumns" class="-mt-4 rounded-t-none border-t-0" />

      <!-- Flush with the bottom (above the phone's bottom bar), so nothing scrolls by below it. -->
      <div ref="foot" class="sticky bottom-(--bottom-nav-height) z-20 -mx-4 -mb-4 border-t border-slate-800 bg-slate-900 px-4 py-2">
        <PeerComposer :recipients="recipients" :placeholder="$t('peers.asUser', { name: userName })">
          <div class="flex items-center gap-1.5 overflow-x-auto text-xs whitespace-nowrap [scrollbar-width:none]">
            <span class="text-slate-500">{{ $t('peers.to') }}</span>
            <button
              type="button"
              class="rounded-full border px-2 py-0.5"
              :class="recipients.includes(EVERYONE) ? chosenClass : 'border-slate-600 text-slate-400'"
              @click="toggleRecipient(EVERYONE)"
            >
              {{ $t('peers.everyone') }}
            </button>
            <button
              v-for="peer in sortedPeers"
              :key="peer.name"
              type="button"
              class="rounded-full border px-2 py-0.5"
              :class="recipients.includes(peer.name) ? chosenClass : 'border-slate-600 text-slate-400'"
              :title="peerTitle(peer)"
              @click="toggleRecipient(peer.name)"
            >
              <span :class="stateColor(peer)">●</span>
              {{ laneLabel(peer.name) }}
            </button>
            <button
              v-for="name in offlineRecipients"
              :key="name"
              type="button"
              class="rounded-full border border-dashed border-sky-500 px-2 py-0.5 text-sky-200"
              :title="$t('peers.offline')"
              @click="toggleRecipient(name)"
            >
              {{ laneLabel(name) }} ✕
            </button>
          </div>
        </PeerComposer>
      </div>
    </template>
  </section>
</template>
