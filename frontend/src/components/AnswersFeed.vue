<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type AnswerText, type Turn } from '../api'
import { markSeen, seenUntil } from '../composables/useAnswerSeen'
import { useSettings } from '../composables/useSettings'
import { sessionName, useSessions } from '../composables/useSessions'
import { type Speakable, useSpeech } from '../composables/useSpeech'
import { useToast } from '../composables/useToast'
import { formatMoment } from '../format'
import { renderMarkdown } from '../markdown'
import AppIcon from './AppIcon.vue'

// What an agent answered, in short: per request of the user its last text (the summary), or
// every text it wrote. Newer answers are marked until they were looked at; any of them can be
// read aloud, or all that follow.
const props = withDefaults(defineProps<{ sessionId: string; turns?: number; controls?: boolean }>(), {
  turns: 20,
  controls: true,
})
const POLL_MS = 4000
const SEEN_AFTER_MS = 2000
const toast = useToast()
const { locale } = useI18n()
const { answersAll } = useSettings()
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
  texts: AnswerText[]
}

const shown = computed<Shown[]>(() =>
  turns.value.map((turn) => ({ turn, texts: answersAll.value ? turn.texts : turn.texts.slice(-1) })),
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
  void speech.play(speakable(all.slice(all.indexOf(text))))
}

function readUnread(): void {
  void speech.play(speakable(unread.value))
}

// For a page that reads the new answers of several agents one after the other.
defineExpose({ unreadTexts: () => speakable(unread.value) })

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

function togglePrompt(id: string): void {
  if (expandedPrompts.value.has(id)) expandedPrompts.value.delete(id)
  else expandedPrompts.value.add(id)
}
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <div v-if="controls" class="flex flex-wrap items-center gap-1.5 border-b border-slate-700 px-2 py-1.5">
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
        <button
          type="button"
          class="text-left text-sm text-slate-400"
          :class="expandedPrompts.has(entry.turn.id) ? 'whitespace-pre-wrap' : 'truncate'"
          @click="togglePrompt(entry.turn.id)"
        >
          {{ entry.turn.prompt }}
        </button>
        <article
          v-for="text in entry.texts"
          :key="text.id"
          class="card flex flex-col gap-2 p-3"
          :class="text.time > seenBefore ? 'border-l-4 border-l-red-500' : ''"
        >
          <div class="markdown note select-text" v-html="renderMarkdown(text.text, null)" />
          <div class="flex items-center gap-2 text-xs text-slate-500">
            <span>{{ formatMoment(new Date(text.time), locale) }}</span>
            <template v-if="speech.available">
              <button
                type="button"
                class="btn-secondary btn-small ml-auto"
                :class="speech.playing.value === text.id ? 'animate-pulse' : ''"
                :title="$t('answers.readThis')"
                @click="void speech.play(speakable([text]))"
              >
                <AppIcon name="speaker" />{{ $t('answers.read') }}
              </button>
              <button type="button" class="btn-secondary btn-small" :title="$t('answers.readFromHereHint')" @click="readFrom(text)">
                {{ $t('answers.readFromHere') }}
              </button>
            </template>
          </div>
        </article>
        <!-- The request being answered right now has no text yet. -->
        <p v-if="!entry.texts.length && entry === shown.at(-1)" class="animate-pulse text-sm text-slate-500">
          {{ $t('answers.working') }}
        </p>
      </section>
    </div>
  </div>
</template>
