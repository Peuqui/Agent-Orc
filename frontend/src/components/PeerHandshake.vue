<script setup lang="ts">
import type { HandshakeTag } from '../peerConversations'

// The handshake's tags of a message as small marks: agreement in green, "not done yet" in amber.
defineProps<{ tags: HandshakeTag[] }>()

const MARKS: Record<HandshakeTag, { symbol: string; classes: string }> = {
  LGTM: { symbol: '✓', classes: 'border-ok-700 text-ok-300' },
  CONTINUE: { symbol: '↻', classes: 'border-highlight-700 text-highlight-300' },
}
</script>

<template>
  <span
    v-for="tag in tags"
    :key="tag"
    class="rounded-full border px-1.5 text-[0.7rem] leading-4"
    :class="MARKS[tag].classes"
    :title="$t(`peers.handshake.${tag}`)"
  >
    {{ MARKS[tag].symbol }} {{ tag }}
  </span>
</template>
