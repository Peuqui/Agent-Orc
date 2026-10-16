<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatTimeSpan } from '../format'
import { clip, laneLabel, type ChatEntry } from '../peerConversations'

// One message in a conversation, as a messenger shows it: a bubble on its sender's side, a
// machine's notice small in the middle. A long text shows its beginning, "more" the rest and what
// came with it; repeats of the same message are one bubble with their count and time span.
const PREVIEW_CHARS = 600
const PREVIEW_LINES = 8

const props = defineProps<{ entry: ChatEntry }>()
const { locale } = useI18n()
const open = ref(false)

const message = computed(() => props.entry.run.message)
const preview = computed(() => clip(message.value.content, PREVIEW_CHARS, PREVIEW_LINES))
const hasMore = computed(() => preview.value !== message.value.content.trim() || message.value.context !== null)
const time = computed(() => formatTimeSpan(new Date(props.entry.run.first), new Date(props.entry.run.last), locale.value))

const BUBBLE_CLASSES = {
  left: 'mr-auto rounded-bl-sm bg-slate-700/70',
  right: 'ml-auto rounded-br-sm bg-sky-900/60',
}
</script>

<template>
  <div
    v-if="entry.side === 'center'"
    class="mx-auto mt-2 max-w-[90%] rounded-md bg-slate-900/60 px-3 py-1 text-center text-xs text-slate-400"
  >
    <span class="mr-1 text-slate-500" :title="message.from">{{ laneLabel(message.from) }}:</span>
    <span class="break-words whitespace-pre-wrap select-text">{{ open ? message.content : preview }}</span>
    <button v-if="hasMore" type="button" class="ml-1 text-sky-300 hover:underline" @click="open = !open">
      {{ open ? $t('peers.less') : $t('peers.more') }}
    </button>
    <span class="ml-1 text-slate-500">
      · <template v-if="entry.run.count > 1">{{ $t('peers.times', { count: entry.run.count }) }} · </template>{{ time }}
    </span>
  </div>
  <div v-else class="w-fit max-w-[85%] rounded-2xl px-3 py-1.5" :class="[BUBBLE_CLASSES[entry.side], entry.showName ? 'mt-3' : 'mt-1']">
    <div v-if="entry.showName" class="text-xs font-medium text-amber-400" :title="message.from">{{ laneLabel(message.from) }}</div>
    <p class="text-sm break-words whitespace-pre-wrap text-slate-100 select-text">{{ open ? message.content : preview }}</p>
    <pre
      v-if="open && message.context"
      class="mt-2 max-h-80 overflow-auto rounded bg-slate-900 p-2 text-xs whitespace-pre-wrap text-slate-400 select-text"
      >{{ message.context }}</pre
    >
    <div class="mt-0.5 flex items-baseline justify-end gap-2 text-[0.7rem] text-slate-400">
      <button v-if="hasMore" type="button" class="mr-auto text-sky-300 hover:underline" @click="open = !open">
        {{ open ? $t('peers.less') : $t('peers.more') }}
      </button>
      <span v-if="message.context">📎</span>
      <span v-if="entry.run.count > 1">{{ $t('peers.times', { count: entry.run.count }) }}</span>
      <span>{{ time }}</span>
    </div>
  </div>
</template>
