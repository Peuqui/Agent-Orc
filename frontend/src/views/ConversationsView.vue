<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type Peer, type PeerEvent, type PeerMessage } from '../api'
import PeerMessageItem from '../components/PeerMessageItem.vue'
import { useSettings } from '../composables/useSettings'
import { useToast } from '../composables/useToast'
import { formatMoment } from '../format'
import { EVERYONE, groupConversations, replyRecipients, type Conversation } from '../peerConversations'

// AI-Connect read along: the conversations between the agents, live, and a field to write to
// them as the user. The server runs AI-Connect's program per open page and hands its lines on;
// when it ends (the bridge restarted, or cannot be reached) the stream ends and the browser
// connects again by itself, getting the history anew. A refused token ends it for good.
const FINAL_ERRORS = new Set(['token_refused', 'token_missing'])

const toast = useToast()
const { locale, t } = useI18n()
const { peerUserToken } = useSettings()

const configured = ref<boolean | null>(null)
const userName = ref('')
const peers = ref<Peer[]>([])
const messages = ref<PeerMessage[]>([])
const known = new Set<number>()
const historyLoaded = ref(false)
const streamError = ref<string | null>(null)
const view = ref<'tree' | 'timeline'>('tree')
const openConversations = ref(new Set<string>())

const recipients = ref<string[]>([])
const text = ref('')
const sending = ref(false)
const tokenDraft = ref('')
const changingToken = ref(false)

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
const peerNames = computed(() => peers.value.map((peer) => peer.name).sort())
// Chosen, but not online now (from an answered conversation): they get it when they come back.
const offlineRecipients = computed(() =>
  recipients.value.filter((recipient) => recipient !== EVERYONE && !peerNames.value.includes(recipient)),
)

function title(conversation: Conversation): string {
  const [first, second] = conversation.members
  return second === EVERYONE ? `${first} → ${t('peers.everyone')}` : `${first} ↔ ${second}`
}

function toggleConversation(key: string): void {
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
  recipients.value = replyRecipients(conversation)
}

function saveToken(): void {
  peerUserToken.value = tokenDraft.value.trim()
  tokenDraft.value = ''
  changingToken.value = false
}

const canSend = computed(
  () => peerUserToken.value !== '' && recipients.value.length > 0 && text.value.trim() !== '' && !sending.value,
)

async function send(): Promise<void> {
  sending.value = true
  try {
    const result = await api.peerMessage(peerUserToken.value, recipients.value, text.value.trim())
    const offline = result.sent.filter((sent) => !sent.online).map((sent) => sent.to)
    text.value = ''
    toast.info(offline.length ? t('peers.sentOffline', { names: offline.join(', ') }) : t('peers.sent'))
  } catch (error) {
    toast.error(error)
  } finally {
    sending.value = false
  }
}
</script>

<template>
  <section class="flex flex-col gap-4">
    <div class="flex flex-wrap items-center gap-2">
      <h1 class="flex-1 text-lg font-semibold">{{ $t('peers.title') }}</h1>
      <div v-if="configured" class="flex overflow-hidden rounded-md border border-slate-600 text-sm">
        <button
          v-for="mode in ['tree', 'timeline'] as const"
          :key="mode"
          class="px-3 py-1"
          :class="view === mode ? 'bg-slate-600 text-slate-100' : 'text-slate-400 hover:bg-slate-700'"
          @click="view = mode"
        >
          {{ $t(`peers.view.${mode}`) }}
        </button>
      </div>
    </div>

    <p v-if="configured === false" class="card p-6 text-center text-slate-400">{{ $t('peers.notConfigured') }}</p>
    <template v-else-if="configured">
      <p v-if="streamError" class="card border-amber-700 p-3 text-sm text-amber-300">
        {{ $t(`peers.streamError.${streamError}`) }}
      </p>

      <div v-if="peers.length" class="flex flex-wrap gap-2 text-xs">
        <span
          v-for="peer in peers"
          :key="peer.name"
          class="rounded-full border border-slate-600 px-2 py-0.5 text-slate-300"
          :title="[peer.state, peer.status].filter(Boolean).join(' · ')"
        >
          <span :class="peer.state === 'busy' ? 'text-amber-400' : 'text-emerald-400'">●</span> {{ peer.name }}
        </span>
      </div>

      <p v-if="!historyLoaded && !streamError" class="card p-6 text-center text-slate-400">{{ $t('peers.loading') }}</p>
      <p v-else-if="historyLoaded && !messages.length" class="card p-6 text-center text-slate-400">
        {{ $t('peers.empty') }}
      </p>

      <div v-else-if="view === 'tree'" class="flex flex-col gap-2">
        <div v-for="conversation in conversations" :key="conversation.key" class="card">
          <div class="flex items-center gap-2 p-3">
            <button
              type="button"
              class="flex min-w-0 flex-1 flex-col text-left"
              :aria-expanded="openConversations.has(conversation.key)"
              @click="toggleConversation(conversation.key)"
            >
              <span class="text-sm font-medium break-words text-amber-400">{{ title(conversation) }}</span>
              <span class="text-xs text-slate-500">
                {{ $t('peers.count', { count: conversation.messages.length }) }} ·
                {{ formatMoment(new Date(conversation.last), locale) }}
              </span>
            </button>
            <button type="button" class="btn-secondary btn-small" @click="answer(conversation)">
              {{ $t('peers.answer') }}
            </button>
          </div>
          <div v-if="openConversations.has(conversation.key)" class="border-t border-slate-700 px-3 pb-1">
            <PeerMessageItem v-for="message in conversation.messages" :key="message.id" :message="message" />
          </div>
        </div>
      </div>

      <div v-else class="card px-3 py-1">
        <PeerMessageItem v-for="message in timeline" :key="message.id" :message="message" />
      </div>

      <form class="card sticky bottom-2 flex flex-col gap-2 p-3" @submit.prevent="send">
        <div v-if="peerUserToken === '' || changingToken" class="flex flex-wrap items-center gap-2">
          <input
            v-model="tokenDraft"
            type="password"
            autocomplete="off"
            class="input min-w-0 flex-1"
            :placeholder="$t('peers.tokenPlaceholder')"
          />
          <button type="button" class="btn-secondary btn-small" :disabled="!tokenDraft.trim()" @click="saveToken">
            {{ $t('peers.tokenSave') }}
          </button>
          <span class="w-full text-xs text-slate-500">{{ $t('peers.tokenHint') }}</span>
        </div>
        <template v-else>
          <div class="flex flex-wrap items-center gap-1.5 text-xs">
            <span class="text-slate-500">{{ $t('peers.to') }}</span>
            <button
              v-for="name in [EVERYONE, ...peerNames]"
              :key="name"
              type="button"
              class="rounded-full border px-2 py-0.5"
              :class="recipients.includes(name) ? 'border-sky-500 bg-sky-900/40 text-sky-200' : 'border-slate-600 text-slate-400'"
              @click="toggleRecipient(name)"
            >
              {{ name === EVERYONE ? $t('peers.everyone') : name }}
            </button>
            <button
              v-for="name in offlineRecipients"
              :key="name"
              type="button"
              class="rounded-full border border-dashed border-sky-500 px-2 py-0.5 text-sky-200"
              :title="$t('peers.offline')"
              @click="toggleRecipient(name)"
            >
              {{ name }} ✕
            </button>
          </div>
          <textarea v-model="text" rows="3" class="input resize-y" :placeholder="$t('peers.asUser', { name: userName })" />
          <div class="flex items-center gap-2">
            <button type="button" class="text-xs text-slate-500 underline" @click="changingToken = true">
              {{ $t('peers.tokenChange') }}
            </button>
            <button type="submit" class="btn-primary btn-small ml-auto" :disabled="!canSend">{{ $t('peers.send') }}</button>
          </div>
        </template>
      </form>
    </template>
  </section>
</template>
