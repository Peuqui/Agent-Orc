<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { triggerRect } from '../trigger'

// Opens right beside the control that opened it: below, or above where there is no room
// below. Without one (none pressed) it is centred, a sheet from the bottom on phones.
defineProps<{ title: string }>()
const emit = defineEmits<{ close: [] }>()

const MARGIN = 8
const card = ref<HTMLElement>()
const anchor = triggerRect()
const place = ref<{ left: string; top: string } | null>(null)

function placeBesideAnchor(): void {
  if (!anchor || !card.value) return
  const { width, height } = card.value.getBoundingClientRect()
  const centred = anchor.left + anchor.width / 2 - width / 2
  const left = Math.min(Math.max(MARGIN, centred), window.innerWidth - width - MARGIN)
  const below = anchor.bottom + MARGIN
  const fitsBelow = below + height <= window.innerHeight - MARGIN
  const top = fitsBelow ? below : Math.max(MARGIN, anchor.top - MARGIN - height)
  place.value = { left: `${left}px`, top: `${top}px` }
}

// Placed again whenever the content changes its size (e.g. once loaded), so it stays on screen.
const resizes = new ResizeObserver(placeBesideAnchor)

onMounted(async () => {
  await nextTick()
  if (!anchor || !card.value) return
  placeBesideAnchor()
  resizes.observe(card.value)
})

onBeforeUnmount(() => resizes.disconnect())
</script>

<template>
  <!-- Drawn into the body: a parent with a filter or blur (the page header) would otherwise
       become the frame "fixed" positions refer to, and the dialog would end up inside it. -->
  <Teleport to="body">
    <div
      class="fixed inset-0 z-40 flex justify-center bg-black/60"
      :class="anchor ? '' : 'items-end sm:items-center'"
      @click.self="emit('close')"
      @keydown.esc="emit('close')"
    >
      <div
        ref="card"
        class="card p-5"
        :class="
          anchor
            ? 'fixed max-h-[calc(100dvh-1rem)] w-[min(28rem,calc(100vw-1rem))] overflow-y-auto'
            : 'w-full max-w-md rounded-b-none sm:rounded-b-xl'
        "
        :style="anchor ? (place ?? { visibility: 'hidden' }) : undefined"
        role="dialog"
        :aria-label="title"
      >
        <h2 class="mb-4 text-lg font-semibold text-slate-100">{{ title }}</h2>
        <slot />
      </div>
    </div>
  </Teleport>
</template>
