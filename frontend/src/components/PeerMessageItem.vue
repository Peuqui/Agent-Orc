<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { PeerMessage } from '../api'
import { formatMoment } from '../format'
import { EVERYONE, firstLine } from '../peerConversations'

// One message of AI-Connect: its first line, the whole text (and what came with it) on a tap.
const FIRST_LINE_CHARS = 140

defineProps<{ message: PeerMessage }>()
const { locale, t } = useI18n()
const open = ref(false)

function recipient(to: string): string {
  return to === EVERYONE ? t('peers.everyone') : to
}
</script>

<template>
  <article class="border-t border-slate-700/60 py-2 first:border-t-0">
    <button type="button" class="w-full text-left" :aria-expanded="open" @click="open = !open">
      <div class="flex flex-wrap items-baseline gap-x-2 text-xs text-slate-500">
        <span>{{ formatMoment(new Date(message.timestamp), locale) }}</span>
        <span class="text-amber-400">{{ message.from }}</span>
        <span>→ <span class="text-amber-400/80">{{ recipient(message.to) }}</span></span>
        <span v-if="message.context">📎</span>
      </div>
      <p v-if="!open" class="mt-0.5 text-sm break-words text-slate-200">{{ firstLine(message.content, FIRST_LINE_CHARS) }}</p>
    </button>
    <template v-if="open">
      <p class="mt-0.5 text-sm break-words whitespace-pre-wrap text-slate-200 select-text">{{ message.content }}</p>
      <pre
        v-if="message.context"
        class="mt-2 max-h-80 overflow-auto rounded bg-slate-900 p-2 text-xs whitespace-pre-wrap text-slate-400 select-text"
        >{{ message.context }}</pre
      >
    </template>
  </article>
</template>
