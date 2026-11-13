<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useToast } from '../composables/useToast'
import { loadPdf, type PdfDocument } from '../pdf'

// The pages of a PDF one below the other, only the first unless `all`. Each page is drawn when it
// comes (nearly) into view, so a long PDF does not slow the page down.
const props = defineProps<{ url: string; all: boolean }>()
const emit = defineEmits<{ loaded: [pageCount: number] }>()
const toast = useToast()
const pageCount = ref(0)
// The first page's canvas is there from the start: it is drawn on as soon as the PDF is loaded.
const shown = computed(() => (props.all ? Math.max(pageCount.value, 1) : 1))
const host = ref<HTMLElement>()
let document_: PdfDocument | null = null
let observer: IntersectionObserver | null = null
const drawn = new Set<number>()

async function draw(canvas: HTMLCanvasElement, pageNumber: number): Promise<void> {
  if (document_ === null || drawn.has(pageNumber)) return
  drawn.add(pageNumber)
  const width = host.value?.clientWidth ?? canvas.clientWidth
  await document_.drawPage(canvas, pageNumber, width)
}

/** Draws each page canvas once it is (nearly) in view. */
function observe(): void {
  observer ??= new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        const canvas = entry.target as HTMLCanvasElement
        observer?.unobserve(canvas)
        void draw(canvas, Number(canvas.dataset.page))
      }
    },
    { rootMargin: '400px' },
  )
  for (const canvas of host.value?.querySelectorAll<HTMLCanvasElement>('canvas[data-page]') ?? []) {
    if (!drawn.has(Number(canvas.dataset.page))) observer.observe(canvas)
  }
}

onMounted(async () => {
  try {
    document_ = await loadPdf(props.url)
    pageCount.value = document_.pageCount
    emit('loaded', document_.pageCount)
    await nextTick()
    observe()
  } catch (error) {
    toast.error(error)
  }
})

watch(shown, async () => {
  await nextTick()
  observe()
})

onBeforeUnmount(() => {
  observer?.disconnect()
  void document_?.destroy()
})
</script>

<template>
  <div ref="host" class="flex flex-col gap-2">
    <canvas
      v-for="page in shown"
      :key="page"
      :data-page="page"
      class="w-full rounded border border-line bg-paper"
    />
  </div>
</template>
