<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type AnswerText, type Interjection, type Turn } from '../api'
import { shownTexts, uploadMentions } from '../answers'
import { markSeen, seenUntil } from '../composables/useAnswerSeen'
import { useAnswersAll } from '../composables/useSettings'
import { sessionName, useSessions } from '../composables/useSessions'
import { type Speakable, useSpeech } from '../composables/useSpeech'
import { useToast } from '../composables/useToast'
import { formatMoment } from '../format'
import { renderMarkdown } from '../markdown'
import AnswerImages from './AnswerImages.vue'
import AppIcon from './AppIcon.vue'

// What an agent answered, in short: per request of the user its last text (the summary), or
// every text it wrote. Newer answers are marked until they were looked at; any of them can be
// read aloud, or all that follow.
const props = withDefaults(defineProps<{ sessionId: string; turns?: number }>(), { turns: 20 })
const POLL_MS = 4000
const SEEN_AFTER_MS = 2000
const toast = useToast()
const { locale } = useI18n()
const answersAll = useAnswersAll(props.sessionId)
const { sessions } = useSessions()
const speech = useSpeech()
const turns = ref<Turn[]>([])
const loaded = ref(false)
const expandedPrompts = ref(new Set<string>())
const box = ref<HTMLElement>()
let timer: number | undefined
let seenTimer: number | undefined
// What was looked at before this view opened: the marks stay until it is closed.
const seenBefore = ref(seenUntil(props.sessionId))

interface Shown {
  turn: Turn
  /** The agent's texts shown (all of them, or the last), for reading aloud. */
  texts: AnswerText[]
  /** What is shown below the request in the order it happened: the agent's texts and what the user typed in between. */
  items: (({ kind: 'agent' } & AnswerText) | ({ kind: 'user' } & Interjection))[]
}

const shown = computed<Shown[]>(() =>
  turns.value.map((turn) => {
    const texts = shownTexts(turn, answersAll.value)
    const items: Shown['items'] = [
      ...texts.map((text) => ({ kind: 'agent' as const, ...text })),
      ...turn.interjections.map((interjection) => ({ kind: 'user' as const, ...interjection })),
    ]
    // ISO times in the same format compare as text.
    return { turn, texts, items: items.sort((a, b) => a.time.localeCompare(b.time)) }
  }),
)
const everyText = computed(() => shown.value.flatMap((entry) => entry.texts))
const newest = computed(() => everyText.value.at(-1)?.time ?? '')
const unread = computed(() => everyText.value.filter((text) => text.time > seenBefore.value))

const agentName = computed(() => {
  const session = sessions.value.find((candidate) => candidate.id === props.sessionId)
  return session ? sessionName(session) : undefined
})

function speakable(texts: AnswerText[]): Speakable[] {
  return texts.map((text) => ({ id: text.id, text: text.text, label: agentName.value }))
}

function readFrom(text: AnswerText): void {
  const all = everyText.value
  void speech.play(speakable(all.slice(all.findIndex((candidate) => candidate.id === text.id))))
}

function readUnread(): void {
  void speech.play(speakable(unread.value))
}



async function load(): Promise<void> {
  const bottomBefore = box.value ? box.value.scrollHeight - box.value.scrollTop - box.value.clientHeight < 80 : true
  try {
    turns.value = await api.answers(props.sessionId, props.turns)
  } catch (error) {
    toast.error(error)
    return
  }
  const first = !loaded.value
  loaded.value = true
  // Following the newest answers, unless the reader has scrolled up.
  if (first || bottomBefore) {
    await nextTick()
    box.value?.scrollTo({ top: box.value.scrollHeight })
  }
  scheduleSeen()
}

// Looked at once it has been on screen for a moment.
function scheduleSeen(): void {
  window.clearTimeout(seenTimer)
  seenTimer = window.setTimeout(() => {
    if (document.visibilityState === 'visible' && newest.value) markSeen(props.sessionId, newest.value)
  }, SEEN_AFTER_MS)
}

onMounted(() => {
  void load()
  timer = window.setInterval(() => {
    if (document.visibilityState === 'visible') void load()
  }, POLL_MS)
})
onBeforeUnmount(() => {
  window.clearInterval(timer)
  window.clearTimeout(seenTimer)
})

/**
 * Where the pictures of a message are served: those the transcript holds (its entry's pictures)
 * and those named by path in its text (attached in Agent-Orc).
 */
function pictureUrls(entryId: string, text: string, images: number): string[] {
  const inTranscript = Array.from({ length: images }, (_, index) => api.answerImageUrl(props.sessionId, entryId, index))
  const attached = uploadMentions(text).files.map((name) => api.uploadUrl(props.sessionId, name))
  return [...inTranscript, ...attached]
}

const FOLD_LINES = 8
const FOLD_CHARS = 600

/** A request longer than this is folded to a few lines until opened. */
function foldable(prompt: string): boolean {
  return prompt.split('\n').length > FOLD_LINES || prompt.length > FOLD_CHARS
}

function togglePrompt(id: string): void {
  if (expandedPrompts.value.has(id)) expandedPrompts.value.delete(id)
  else expandedPrompts.value.add(id)
}
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <div class="flex flex-wrap items-center gap-1.5 border-b border-slate-700 px-2 py-1.5">
      <button
        type="button"
        class="btn-secondary btn-small"
        :title="$t('answers.allHint')"
        @click="answersAll = !answersAll"
      >
        {{ answersAll ? $t('answers.showSummaries') : $t('answers.showAll') }}
      </button>
      <template v-if="speech.available">
        <button
          type="button"
          class="btn-primary btn-small"
          :disabled="!unread.length"
          :title="$t('answers.readNewHint')"
          @click="readUnread"
        >
          <AppIcon name="speaker" />{{ $t('answers.readNew', { count: unread.length }) }}
        </button>
        <template v-if="speech.playing.value !== null">
          <button type="button" class="btn-secondary btn-small-icon" :title="$t('answers.pause')" :aria-label="$t('answers.pause')" @click="speech.togglePause">
            <AppIcon :name="speech.paused.value ? 'play' : 'pause'" />
          </button>
          <button type="button" class="btn-secondary btn-small-icon" :title="$t('answers.stop')" :aria-label="$t('answers.stop')" @click="speech.stop">
            <AppIcon name="stop" />
          </button>
        </template>
      </template>
    </div>
    <div ref="box" class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-3">
      <p v-if="loaded && !turns.length" class="text-slate-400">{{ $t('answers.empty') }}</p>
      <section v-for="entry in shown" :key="entry.turn.id" class="flex flex-col gap-2">
        <!-- What the user asked, in full; a very long request is folded. -->
        <div class="rounded-lg border-l-4 border-sky-700/70 bg-sky-950/40 px-3 py-2 text-sm text-slate-300">
          <p
            v-if="uploadMentions(entry.turn.prompt).text"
            class="whitespace-pre-wrap break-words"
            :class="foldable(entry.turn.prompt) && !expandedPrompts.has(entry.turn.id) ? 'line-clamp-6' : ''"
          >{{ uploadMentions(entry.turn.prompt).text }}</p>
          <AnswerImages :urls="pictureUrls(entry.turn.id, entry.turn.prompt, entry.turn.images)" />
          <button v-if="foldable(entry.turn.prompt)" type="button" class="mt-1 text-xs text-slate-500 underline" @click="togglePrompt(entry.turn.id)">
            {{ expandedPrompts.has(entry.turn.id) ? $t('answers.less') : $t('answers.more') }}
          </button>
        </div>
        <template v-for="item in entry.items" :key="item.id">
          <!-- Typed while the agent was answering. -->
          <div
            v-if="item.kind === 'user'"
            class="ml-4 rounded-lg border-l-4 border-sky-700/70 bg-sky-950/40 px-3 py-2 text-sm text-slate-300"
            :class="item.pending ? 'opacity-60' : ''"
          >
            <p v-if="uploadMentions(item.text).text" class="whitespace-pre-wrap break-words">{{ uploadMentions(item.text).text }}</p>
            <AnswerImages :urls="pictureUrls(item.id, item.text, item.images)" />
            <p class="mt-1 text-xs text-slate-500">
              {{ $t('answers.interjection') }} · {{ formatMoment(new Date(item.time), locale) }}
              <span v-if="item.pending"> · {{ $t('answers.pending') }}</span>
            </p>
          </div>
          <article
            v-else
            class="card flex flex-col gap-2 p-3"
            :class="item.time > seenBefore ? 'border-l-4 border-l-red-500' : ''"
          >
            <div class="markdown note select-text" v-html="renderMarkdown(item.text, null)" />
            <div class="flex items-center gap-2 text-xs text-slate-500">
              <span>{{ formatMoment(new Date(item.time), locale) }}</span>
              <template v-if="speech.available">
                <button
                  type="button"
                  class="btn-secondary btn-small ml-auto"
                  :class="speech.playing.value === item.id ? 'animate-pulse' : ''"
                  :title="$t('answers.readThis')"
                  @click="void speech.play(speakable([item]))"
                >
                  <AppIcon name="speaker" />{{ $t('answers.read') }}
                </button>
                <button type="button" class="btn-secondary btn-small" :title="$t('answers.readFromHereHint')" @click="readFrom(item)">
                  {{ $t('answers.readFromHere') }}
                </button>
              </template>
            </div>
          </article>
        </template>
        <!-- The request being answered right now has no text yet. -->
        <p v-if="!entry.texts.length && entry === shown.at(-1)" class="animate-pulse text-sm text-slate-500">
          {{ $t('answers.working') }}
        </p>
      </section>
    </div>
  </div>
</template>
