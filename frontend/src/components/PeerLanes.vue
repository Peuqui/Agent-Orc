<script setup lang="ts">
import { computed } from 'vue'
import type { PeerMessage } from '../api'
import { arrowOf, laneLabel, lanesOf } from '../peerConversations'
import PeerMessageItem from './PeerMessageItem.vue'

// The messages as a sequence diagram: a lane for everyone taking part, each message an arrow from
// its sender's lane to its receiver's (a broadcast reaches across all lanes), its text below.
const props = defineProps<{ messages: PeerMessage[] }>()

const lanes = computed(() => lanesOf(props.messages))
const columns = computed(() => ({ gridTemplateColumns: `repeat(${lanes.value.length}, minmax(0, 1fr))` }))

/** The middle of a lane, in percent of the width. */
function middle(lane: number): number {
  return ((lane + 0.5) / lanes.value.length) * 100
}

function arrow(message: PeerMessage) {
  const { from, to } = arrowOf(message, lanes.value)
  const ends = to === null ? [0, lanes.value.length - 1] : [from, to]
  const left = middle(Math.min(...ends))
  return {
    from,
    to,
    bar: { left: `${left}%`, width: `${middle(Math.max(...ends)) - left}%` },
    // The tip points away from the sender.
    rightwards: to !== null && to > from,
  }
}
</script>

<template>
  <div class="card px-3 pb-2">
    <div class="sticky top-(--app-header-height) z-10 grid gap-1 border-b border-slate-700 bg-slate-800 py-2" :style="columns">
      <span v-for="lane in lanes" :key="lane" class="truncate text-center text-xs font-medium text-amber-400" :title="lane">
        {{ laneLabel(lane) }}
      </span>
    </div>
    <div class="relative">
      <div class="pointer-events-none absolute inset-0 grid" :style="columns" aria-hidden="true">
        <div v-for="lane in lanes" :key="lane" class="mx-auto w-px bg-slate-600/60" />
      </div>
      <div v-for="message in messages" :key="message.id" class="relative border-b border-slate-700/50 pt-2 last:border-b-0">
        <div class="relative h-3" aria-hidden="true">
          <template v-for="shape in [arrow(message)]" :key="message.id">
            <span class="absolute top-1/2 h-0.5 -translate-y-1/2 bg-amber-400" :style="shape.bar" />
            <span
              class="absolute top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-amber-400"
              :style="{ left: `${middle(shape.from)}%` }"
            />
            <!-- The tip at the receiver; a broadcast marks every lane it reaches. -->
            <span
              v-if="shape.to !== null"
              class="absolute top-1/2 size-0 -translate-y-1/2 border-y-[5px] border-y-transparent"
              :class="shape.rightwards ? '-translate-x-full border-l-[8px] border-l-amber-400' : 'border-r-[8px] border-r-amber-400'"
              :style="{ left: `${middle(shape.to)}%` }"
            />
            <template v-else>
              <span
                v-for="(_lane, index) in lanes"
                v-show="index !== shape.from"
                :key="index"
                class="absolute top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-amber-400 bg-slate-800"
                :style="{ left: `${middle(index)}%` }"
              />
            </template>
          </template>
        </div>
        <PeerMessageItem :message="message" class="relative border-t-0 bg-slate-800/90 pt-1" />
      </div>
    </div>
  </div>
</template>
