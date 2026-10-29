<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePeerColor } from '../composables/usePeerColors'
import { formatTimeSpan } from '../format'
import { clip, EVERYONE, isMachine, laneLabel, readableOf, type MessageRun } from '../peerConversations'
import PeerHandshake from './PeerHandshake.vue'

// One message of AI-Connect: its first line, the whole text (and what came with it) on a tap.
// Only its time: the day stands above it. Repeats of it are one row with their count; the
// handshake's tags are marks beside the names.
const FIRST_LINE_CHARS = 140

const props = defineProps<{ run: MessageRun }>()
const { locale, t } = useI18n()
const colorOf = usePeerColor()
const open = ref(false)
const readable = computed(() => readableOf(props.run.message))

function recipient(to: string): string {
  return to === EVERYONE ? t('peers.everyone') : laneLabel(to)
}
</script>

<template>
  <article class="border-t border-line/60 py-2 first:border-t-0">
    <button type="button" class="press-row -mx-1 block w-[calc(100%+0.5rem)] px-1 text-left" :aria-expanded="open" @click="open = !open">
      <div class="flex flex-wrap items-baseline gap-x-2 text-xs text-muted">
        <span>{{ formatTimeSpan(new Date(run.first), new Date(run.last), locale) }}</span>
        <!-- Short names (without the host); the whole name on hover. -->
        <span :class="colorOf(run.message.from)" :title="run.message.from">{{ laneLabel(run.message.from) }}</span>
        <span>→ <span :class="colorOf(run.message.to)" :title="run.message.to">{{ recipient(run.message.to) }}</span></span>
        <PeerHandshake :tags="readable.tags" />
        <span v-if="run.count > 1">{{ $t('peers.times', { count: run.count }) }}</span>
        <span v-if="run.message.context">📎</span>
      </div>
      <!-- A machine's notices (the bridge) step back behind what the agents write. -->
      <p
        v-if="!open"
        class="mt-0.5 text-sm break-words"
        :class="isMachine(run.message.from) ? 'text-dim' : 'text-main'"
      >
        {{ clip(readable.text, FIRST_LINE_CHARS, 1) }}
      </p>
    </button>
    <template v-if="open">
      <p class="mt-0.5 text-sm break-words whitespace-pre-wrap text-main select-text">{{ readable.text }}</p>
      <pre
        v-if="run.message.context"
        class="mt-2 max-h-80 overflow-auto rounded bg-page p-2 text-xs whitespace-pre-wrap text-dim select-text"
        >{{ run.message.context }}</pre
      >
    </template>
  </article>
</template>
