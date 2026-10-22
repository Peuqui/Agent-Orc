<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useSettings } from '../composables/useSettings'
import { triggerRect } from '../trigger'

// Opens right beside the control that opened it: below, or above where there is no room
// below. Without one (none pressed) it is centred, a sheet from the bottom on phones.
// `tall`, for a dialog with a long list: always centred, as high as the screen; the list scrolls
// (the one thing that does) between the title and the buttons.
// `near`, the place of a control the dialog belongs to (the menu button of the settings): it opens beside that
// one instead of beside what was pressed last.
// A dialog is a control: it takes the controls' size (`.controls-zoom`), like the menu that opened it. The
// screen's units (vw, dvh) are zoomed along, so its limits are divided by the zoom.
const props = defineProps<{ title: string; tall?: boolean; near?: DOMRect | null }>()
const emit = defineEmits<{ close: [] }>()

const MARGIN = 8
const card = ref<HTMLElement>()
const anchor = props.tall ? null : (props.near ?? triggerRect())
const place = ref<{ left: string; top: string } | null>(null)
const { controlsScale } = useSettings()

function placeBesideAnchor(): void {
  if (!anchor || !card.value) return
  // Measured on the screen; the card's own left and top are zoomed along with it.
  const zoom = controlsScale.value / 100
  const { width, height } = card.value.getBoundingClientRect()
  const centred = anchor.left + anchor.width / 2 - width / 2
  const left = Math.min(Math.max(MARGIN, centred), window.innerWidth - width - MARGIN)
  const below = anchor.bottom + MARGIN
  const fitsBelow = below + height <= window.innerHeight - MARGIN
  const top = fitsBelow ? below : Math.max(MARGIN, anchor.top - MARGIN - height)
  place.value = { left: `${left / zoom}px`, top: `${top / zoom}px` }
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
      class="controls-zoom fixed inset-0 z-40 flex justify-center bg-black/60"
      data-modal
      :class="anchor ? '' : tall ? 'items-center' : 'items-end sm:items-center'"
      @click.self="emit('close')"
      @keydown.esc="emit('close')"
    >
      <div
        ref="card"
        class="card p-5"
        :class="
          anchor
            ? 'fixed max-h-[calc((100dvh-1rem)/var(--controls-zoom))] w-[min(28rem,calc((100vw-1rem)/var(--controls-zoom)))] overflow-y-auto'
            : tall
              ? 'flex h-[calc((100dvh-1rem)/var(--controls-zoom))] w-[min(36rem,calc((100vw-1rem)/var(--controls-zoom)))] flex-col'
              : 'max-h-[calc((100dvh-1rem)/var(--controls-zoom))] w-full max-w-md overflow-y-auto rounded-b-none sm:rounded-b-xl'
        "
        :style="anchor ? (place ?? { visibility: 'hidden' }) : undefined"
        role="dialog"
        :aria-label="title"
      >
        <h2 class="mb-4 shrink-0 text-lg font-semibold text-amber-400">{{ title }}</h2>
        <!-- With `tall` the content fills what is left of the card, so that its own list can scroll. -->
        <div :class="tall ? 'flex min-h-0 flex-1 flex-col' : ''"><slot /></div>
      </div>
    </div>
  </Teleport>
</template>
