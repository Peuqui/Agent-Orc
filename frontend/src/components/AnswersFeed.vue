<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type AnswerText, type Interjection, type SpokenRequest, type Turn } from '../api'
import { isUnread, shownTexts, spokenAs, uploadMentions } from '../answers'
import { summaryOf } from '../speechText'
import { markSeen, seenUntil } from '../composables/useAnswerSeen'
import { useAnswerFileLinks } from '../composables/useAnswerFileLinks'
import { useAnswersAll } from '../composables/useAnswersAll'
import { useFeedScroll } from '../composables/useFeedScroll'
import { useViewZoom } from '../composables/useViewZoom'
import { sessionName, useSessions } from '../composables/useSessions'
import { useSpeech } from '../composables/useSpeech'
import { useToast } from '../composables/useToast'
import { formatMoment } from '../format'
import { LISTEN_REPLAY_CLASS, renderMarkdown } from '../markdown'
import { READS_HERE, type Speakable } from '../speechHost'
import AnswerImages from './AnswerImages.vue'
import FoldedText from './FoldedText.vue'
import AppIcon from './AppIcon.vue'
import JogScroller from './JogScroller.vue'

// What an agent answered, in short: per request of the user its last text (the summary), or
// every text it wrote. Newer answers stay marked until they are marked as read (the check, here
// or in the workspace's header) or were read aloud; any of them can be read aloud, or all that
// follow.
const props = withDefaults(defineProps<{ sessionId: string; turns?: number }>(), { turns: 20 })
const toast = useToast()
const { locale } = useI18n()
const answersAll = useAnswersAll(props.sessionId)
const { sessions } = useSessions()
const session = computed(() => sessions.value.find((candidate) => candidate.id === props.sessionId))
const speech = useSpeech()
const turns = ref<Turn[]>([])
const spoken = ref<SpokenRequest[]>([])
const loaded = ref(false)
const box = ref<HTMLElement>()
const zoomed = ref<HTMLElement>()
const { zoomStyle } = useViewZoom(zoomed, box)
// The files and folders the answers name open on a click, as in the terminal.
useAnswerFileLinks(zoomed, () => session.value?.path)
// Read up to this time, the same in every view and on every device (the server keeps one time per agent).
const seen = computed(() => seenUntil(props.sessionId))

/** An answer read to its end counts as read, and so do the older ones. */
function markReadAloud(item: Speakable): void {
  const text = everyText.value.find((candidate) => candidate.id === item.id)
  if (text) markSeen(props.sessionId, text.time)
}

/** Everything there is counts as read, without reading it aloud. */
function markAllSeen(): void {
  const newest = unread.value.at(-1)
  if (newest) markSeen(props.sessionId, newest.time)
}

/** A click on an answer marks it and every one above it (the older ones) as read: one reads from
 * the top, what is below stays new, and the check marks the rest. Not a click on a button or link,
 * and not while text is being selected. */
function markUpTo(event: MouseEvent, clicked: AnswerText): void {
  if ((event.target as Element).closest('button, a, input, select, textarea, audio, .file-link')) return
  if (window.getSelection()?.isCollapsed === false) return
  markSeen(props.sessionId, clicked.time)
}

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
const unread = computed(() => everyText.value.filter((text) => isUnread(text, seen.value)))

const agentName = computed(() => (session.value ? sessionName(session.value) : props.sessionId))

// The list is drawn anew whenever something it shows changes (a poll, the count of new answers below
// while scrolling); turning markdown into HTML is by far the dearest part of that, slow on an old
// tablet, so each answer's HTML is made once.
const htmlOf = new Map<string, string>()

function answerHtml(text: AnswerText): string {
  const markdown = answersAll.value ? text.text : summaryOf(text.text)
  const listenButton = speech.available.value
  const key = `${listenButton}:${markdown}`
  let html = htmlOf.get(key)
  if (html === undefined) {
    html = renderMarkdown(markdown, null, listenButton)
    htmlOf.set(key, html)
  }
  return html
}

function speakable(texts: AnswerText[]): Speakable[] {
  return texts.map((text) => ({ id: text.id, text: text.text, label: agentName.value }))
}

/** A click on the marker of the paragraph for listening reads this answer again. */
function readAgain(event: MouseEvent, text: AnswerText): void {
  if (!(event.target instanceof Element) || !event.target.closest(`.${LISTEN_REPLAY_CLASS}`)) return
  speech.play(speakable([text]), markReadAloud)
}

function readFrom(text: AnswerText): void {
  const all = everyText.value
  speech.play(speakable(all.slice(all.findIndex((candidate) => candidate.id === text.id))), markReadAloud)
}

function readUnread(): void {
  speech.play(speakable(unread.value), markReadAloud)
}



// Where the list goes when something comes in (the rules are in feedScroll.ts).
const { unreadBelow, countUnreadBelow, place, onScroll, takenByHand, showNewBelow, followSpeech } = useFeedScroll(
  box,
  props.sessionId,
  () => unread.value.map((text) => text.id),
)
// Marked as read elsewhere, or new ones arriving, change what lies below without a scroll.
watch(unread, countUnreadBelow, { flush: 'post' })

// Every message of the feed at the last look: what is not in it is new.
let known: Set<string> | null = null

async function load(): Promise<void> {
  try {
    ;[turns.value, spoken.value] = await Promise.all([api.answers(props.sessionId, props.turns), api.spoken(props.sessionId)])
  } catch (error) {
    toast.error(error)
    return
  }
  const first = !loaded.value
  loaded.value = true
  // A request is the reader's own, and so is what the reader typed in between; the rest are the agent's answers.
  const messages = shown.value.flatMap((entry) => [
    { id: entry.turn.id, own: true },
    ...entry.items.map((item) => ({ id: item.id, own: item.kind === 'user' })),
  ])
  const fresh = known === null ? [] : messages.filter((message) => !known?.has(message.id))
  known = new Set(messages.map((message) => message.id))
  // The request and its answer can come in together: then the answer counts alone (its top is shown), as
  // the request would take the list to the end and the answer may not go back up.
  const answers = fresh.filter((message) => !message.own).length
  if (first) await place('opened')
  else if (answers > 0) await place('answer')
  else if (fresh.length > 0) await place('own')
}

// What is read aloud comes into view and gets a quiet highlight; once it was spoken it counts as read.
watch(
  () => speech.playing.value,
  (id, before) => {
    if (id !== null) followSpeech(id, before === null)
  },
)

// Loaded again only when the agent wrote to its conversation: the agent list the app polls anyway
// says so, instead of a request of each view every few seconds.
onMounted(() => void load())
watch(() => session.value?.transcript_version, () => void load())

/**
 * Where the pictures of a message are served: those the transcript holds (its entry's pictures)
 * and those named by path in its text (attached in Agent-Orc).
 */
function pictureUrls(entryId: string, text: string, images: number): string[] {
  const inTranscript = Array.from({ length: images }, (_, index) => api.answerImageUrl(props.sessionId, entryId, index))
  const attached = uploadMentions(text).files.map((name) => api.uploadUrl(props.sessionId, name))
  return [...inTranscript, ...attached]
}

// How many lines of a message of the user are shown before "more", in either view.
const USER_LINES = 2
// One jog "line" in pixels: about the line height of the answers' text.
const JOG_LINE_PX = 24

function jog(lines: number): void {
  takenByHand()
  box.value?.scrollBy({ top: lines * JOG_LINE_PX })
}
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <div class="controls-zoom flex flex-wrap items-center gap-1.5 border-b border-line px-2 py-1.5">
      <!-- What is shown now is highlighted: a summary for each message of yours, or every text. -->
      <div class="flex overflow-hidden rounded-md border border-line-strong text-xs" role="group" :aria-label="$t('answers.mode')">
        <button
          type="button"
          class="px-2.5 py-1.5"
          :class="!answersAll ? 'segment-on' : 'text-dim hover:bg-raised'"
          :aria-pressed="!answersAll"
          :title="$t('answers.summariesHint')"
          @click="answersAll = false"
        >
          {{ $t('answers.modeSummaries') }}
        </button>
        <button
          type="button"
          class="border-l border-line-strong px-2.5 py-1.5"
          :class="answersAll ? 'segment-on' : 'text-dim hover:bg-raised'"
          :aria-pressed="answersAll"
          :title="$t('answers.allHint')"
          @click="answersAll = true"
        >
          {{ $t('answers.modeAll') }}
        </button>
      </div>
      <!-- Everything as read at once, without reading it aloud or scrolling through it. Red while
           there is something new, grey and dead when there is not. -->
      <button
        type="button"
        class="btn-small-icon"
        :class="unread.length ? 'btn-primary' : 'btn-secondary'"
        :disabled="!unread.length"
        :title="$t('answers.markAllSeen')"
        :aria-label="$t('answers.markAllSeen')"
        @click="markAllSeen"
      >
        <AppIcon name="check" />
      </button>
      <template v-if="speech.available.value">
        <button
          type="button"
          class="btn-small"
          :class="unread.length ? 'btn-primary' : 'btn-secondary'"
          :disabled="!unread.length"
          :title="$t('answers.readNewHint')"
          @click="readUnread"
        >
          <AppIcon name="speaker" />{{ $t('answers.readNew', { count: unread.length }) }}
        </button>
        <!-- In a workspace column, pause and stop are in the workspace's header. -->
        <template v-if="READS_HERE && speech.playing.value !== null">
          <button type="button" class="btn-secondary btn-small-icon" :title="$t('answers.pause')" :aria-label="$t('answers.pause')" @click="speech.togglePause">
            <AppIcon :name="speech.paused.value ? 'play' : 'pause'" />
          </button>
          <button type="button" class="btn-secondary btn-small-icon" :title="$t('answers.stop')" :aria-label="$t('answers.stop')" @click="speech.stop">
            <AppIcon name="stop" />
          </button>
        </template>
      </template>
      <!-- Away from the terminal, this shows that the agent is still working on an answer. -->
    </div>
    <div class="relative flex min-h-0 flex-1">
    <div
      ref="box"
      class="min-h-0 min-w-0 flex-1 overflow-y-auto p-3 [scrollbar-width:none]"
      @scroll.passive="onScroll"
      @wheel.passive="takenByHand"
      @touchstart.passive="takenByHand"
    >
    <!-- Scaled as a whole (the device's size for views), so all sizes keep their proportions. -->
    <div ref="zoomed" class="flex flex-col gap-4" :style="zoomStyle">
      <p v-if="loaded && !turns.length" class="text-dim">{{ $t('answers.empty') }}</p>
      <section v-for="entry in shown" :key="entry.turn.id" class="flex flex-col gap-2">
        <!-- What the user asked: a few lines, more on a click. -->
        <div :data-anchor="entry.turn.id" class="rounded-lg border-l-4 border-info-700/70 bg-info-950/40 px-3 py-2 text-sm text-soft">
          <FoldedText v-if="uploadMentions(entry.turn.prompt).text" :text="uploadMentions(entry.turn.prompt).text" :lines="USER_LINES" />
          <AnswerImages :urls="pictureUrls(entry.turn.id, entry.turn.prompt, entry.turn.images)" />
          <!-- Said on the Echo: as the recognition heard it, to compare with the recording. -->
          <div v-if="spokenAs(entry.turn, spoken)" class="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
            <AppIcon name="mic" />
            <span>{{ $t('answers.spoken', { heard: spokenAs(entry.turn, spoken)?.heard }) }}</span>
            <audio
              v-if="spokenAs(entry.turn, spoken)?.recording"
              controls
              preload="none"
              class="h-8 max-w-full"
              :src="api.recordingUrl(spokenAs(entry.turn, spoken)?.id ?? '')"
            />
          </div>
        </div>
        <template v-for="item in entry.items" :key="item.id">
          <!-- Typed while the agent was answering. -->
          <div
            v-if="item.kind === 'user'"
            :data-anchor="item.id"
            class="ml-4 rounded-lg border-l-4 border-info-700/70 bg-info-950/40 px-3 py-2 text-sm text-soft"
            :class="item.pending ? 'opacity-60' : ''"
          >
            <FoldedText v-if="uploadMentions(item.text).text" :text="uploadMentions(item.text).text" :lines="USER_LINES" />
            <AnswerImages :urls="pictureUrls(item.id, item.text, item.images)" />
            <p class="mt-1 text-xs text-muted">
              {{ $t('answers.interjection') }} · {{ formatMoment(new Date(item.time), locale) }}
              <span v-if="item.pending"> · {{ $t('answers.pending') }}</span>
            </p>
          </div>
          <!-- The red edge is 3px thicker than the card's own; the padding gives them back, so the text
               neither moves nor wraps differently when the answer is marked as read. -->
          <article
            v-else
            :data-anchor="item.id"
            class="card flex flex-col gap-2 p-3"
            :class="[
              isUnread(item, seen) ? 'border-l-4 border-l-accent-500 pl-[calc(0.75rem-3px)]' : '',
              speech.playing.value === item.id ? 'ring-1 ring-highlight-500 bg-panel/70' : '',
            ]"
            :title="isUnread(item, seen) ? $t('answers.clickToMark') : undefined"
            @click="markUpTo($event, item)"
          >
            <div
              class="markdown note select-text"
              @click="readAgain($event, item)"
              v-html="answerHtml(item)"
            />
            <div class="flex items-center gap-2 text-xs text-muted">
              <span>{{ formatMoment(new Date(item.time), locale) }}</span>
              <template v-if="speech.available.value">
                <button
                  type="button"
                  class="btn-secondary btn-small-icon ml-auto"
                  :class="speech.playing.value === item.id ? 'animate-pulse' : ''"
                  :title="$t('answers.readThis')"
                  :aria-label="$t('answers.readThis')"
                  @click="speech.play(speakable([item]), markReadAloud)"
                >
                  <AppIcon name="speaker" />
                </button>
                <button
                  type="button"
                  class="btn-secondary btn-small-icon"
                  :title="$t('answers.readFromHereHint')"
                  :aria-label="$t('answers.readFromHereHint')"
                  @click="readFrom(item)"
                >
                  <AppIcon name="speakerFrom" />
                </button>
              </template>
            </div>
          </article>
        </template>
        <!-- The request being answered right now has no text yet. -->
        <p v-if="!entry.texts.length && entry === shown.at(-1)" class="text-sm text-muted">
          {{ $t('answers.working') }}
        </p>
      </section>
    </div>
    </div>
    <!-- Unread answers below the view: one button to the first of them. -->
    <button
      v-if="unreadBelow > 0"
      type="button"
      class="btn-primary btn-small absolute bottom-3 left-1/2 -translate-x-1/2 shadow-lg"
      @click="showNewBelow"
    >
      ↓ {{ $t('answers.newBelow', { count: unreadBelow }) }}
    </button>
    <JogScroller @scroll="jog" />
    </div>
  </div>
</template>
