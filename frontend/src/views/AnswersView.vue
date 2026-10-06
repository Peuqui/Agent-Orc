<script setup lang="ts">
import { computed, ref } from 'vue'
import AnswersFeed from '../components/AnswersFeed.vue'
import AppIcon from '../components/AppIcon.vue'
import { useSettings } from '../composables/useSettings'
import { type Speakable, useSpeech } from '../composables/useSpeech'
import { sessionName, useSessions } from '../composables/useSessions'

// What all running agents answered lately, one below the other: the newest answers are marked
// until they were looked at, any can be read aloud, and one button reads all the new ones.
const LATEST_TURNS = 2
const { sessions } = useSessions()
const { answersAllOnPage } = useSettings()
const speech = useSpeech()
const feeds = ref<Record<string, InstanceType<typeof AnswersFeed> | null>>({})
// Agents with a terminal of their own only (a plain shell has no answers).
const agents = computed(() => sessions.value.filter((session) => session.running && !session.terminal))

function readAllNew(): void {
  const items: Speakable[] = Object.values(feeds.value).flatMap((feed) => feed?.unreadTexts() ?? [])
  void speech.play(items)
}
</script>

<template>
  <section class="flex flex-col gap-3">
    <div class="flex flex-wrap items-center gap-1.5">
      <button type="button" class="btn-secondary btn-small" :title="$t('answers.allHint')" @click="answersAllOnPage = !answersAllOnPage">
        {{ answersAllOnPage ? $t('answers.showSummaries') : $t('answers.showAll') }}
      </button>
      <template v-if="speech.available">
        <button type="button" class="btn-primary btn-small" :title="$t('answers.readNewHint')" @click="readAllNew">
          <AppIcon name="speaker" />{{ $t('answers.readAllNew') }}
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
    <p v-if="!agents.length" class="text-slate-400">{{ $t('answers.noAgents') }}</p>
    <ul class="grid grid-cols-[repeat(auto-fill,minmax(min(26rem,100%),1fr))] gap-3">
      <li v-for="session in agents" :key="session.id" class="card flex flex-col">
        <div class="flex items-center gap-2 border-b border-slate-700 px-3 py-2">
          <h2 class="min-w-0 flex-1 truncate font-semibold">{{ sessionName(session) }}</h2>
          <span v-if="session.busy" class="animate-pulse rounded-full bg-amber-900/40 px-2.5 py-0.5 text-xs font-medium text-amber-300">
            {{ $t('sessions.working') }}
          </span>
          <RouterLink :to="`/terminal/${encodeURIComponent(session.id)}`" class="btn-secondary btn-small">
            <AppIcon name="agents" />{{ $t('answers.open') }}
          </RouterLink>
        </div>
        <div class="flex max-h-96 min-h-32 flex-col">
          <AnswersFeed :ref="(feed) => (feeds[session.id] = feed as InstanceType<typeof AnswersFeed> | null)" :session-id="session.id" :turns="LATEST_TURNS" :controls="false" :all="answersAllOnPage" />
        </div>
      </li>
    </ul>
  </section>
</template>
