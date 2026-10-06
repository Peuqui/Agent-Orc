<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'

// Fast scrolling for a history whose length nobody outside the agent knows (Claude Code keeps
// it itself, full screen): a grip that scrolls while it is pulled away from the middle, the
// faster the further, and springs back when released. Mouse and finger alike. A touch anywhere
// on the track grabs the grip, so the track is wide (a finger needs about 40 px, and the
// phones' own edge gesture eats the outermost ones; see TRACK_WIDTH_PX).
const emit = defineEmits<{ scroll: [lines: number] }>()

// Track width in pixels, the one place it is set for every view that has a jog. A finger needs
// about 40 px, a mouse less; kept a little under that, as the grip is touched on the whole track.
const TRACK_WIDTH_PX = 16
// Pulls shorter than this do nothing, so a grip that is merely touched stays still.
const DEAD_ZONE_PX = 6
// At the end of the track the history moves at this many lines per second; kept moderate, as
// a jog overshoots easily.
const MAX_LINES_PER_SECOND = 100
// Cubic: slow over most of the way, fast only near the end of the track.
const SPEED_CURVE = 3
const MILLISECONDS_PER_SECOND = 1000

const track = ref<HTMLElement>()
/** Grip offset from the middle in pixels; negative is up (towards older output). */
const offset = ref(0)
const pulling = ref(false)
let pointerId: number | null = null
let frame: number | null = null
let pending = 0

function speed(): number {
  const reach = (track.value?.clientHeight ?? 0) / 2
  const pull = Math.abs(offset.value) - DEAD_ZONE_PX
  if (reach <= DEAD_ZONE_PX || pull <= 0) return 0
  return Math.sign(offset.value) * (pull / (reach - DEAD_ZONE_PX)) ** SPEED_CURVE * MAX_LINES_PER_SECOND
}

function run(): void {
  let previous = performance.now()
  const step = (now: number): void => {
    pending += (speed() * (now - previous)) / MILLISECONDS_PER_SECOND
    previous = now
    const lines = Math.trunc(pending)
    if (lines !== 0) {
      pending -= lines
      emit('scroll', lines)
    }
    frame = requestAnimationFrame(step)
  }
  frame = requestAnimationFrame(step)
}

function stop(): void {
  if (frame !== null) cancelAnimationFrame(frame)
  frame = null
  pointerId = null
  pulling.value = false
  offset.value = 0
  pending = 0
}

function follow(event: PointerEvent): void {
  const box = track.value?.getBoundingClientRect()
  if (!box) return
  const reach = box.height / 2
  offset.value = Math.max(-reach, Math.min(reach, event.clientY - (box.top + reach)))
}

function onPointerDown(event: PointerEvent): void {
  if (event.button !== 0) return
  pointerId = event.pointerId
  pulling.value = true
  // Keeps the pointer events coming while the pointer leaves the narrow track.
  const grip = event.currentTarget as HTMLElement
  grip.setPointerCapture(event.pointerId)
  follow(event)
  run()
}

function onPointerMove(event: PointerEvent): void {
  if (event.pointerId === pointerId) follow(event)
}

onBeforeUnmount(stop)
</script>

<template>
  <div
    ref="track"
    class="relative shrink-0 cursor-ns-resize touch-none select-none"
    :style="{ width: `${TRACK_WIDTH_PX}px` }"
    :title="$t('terminal.jog')"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="stop"
    @pointercancel="stop"
  >
    <div class="absolute inset-y-2 left-1/2 w-0.5 -translate-x-1/2 rounded-full bg-slate-700" />
    <div
      class="absolute top-1/2 left-1/2 h-12 w-full -translate-x-1/2 -translate-y-1/2 rounded-full border border-slate-500 bg-slate-600"
      :class="{ 'border-amber-300 bg-amber-300/30': pulling }"
      :style="{ marginTop: `${offset}px` }"
    />
  </div>
</template>
