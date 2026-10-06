<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useToast } from '../composables/useToast'
import { loadPdf, type PdfDocument } from '../pdf'
import AppIcon from './AppIcon.vue'

// A PDF of a note: the first page as a preview, on request all pages one below the other. The
// pages are drawn when they come into view, so a long PDF does not slow the note down.
const props = defineProps<{ url: string; name: string }>()
const toast = useToast()
const pageCount = ref(0)
const expanded = ref(false)
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

onMounted(async () => {
  try {
    document_ = await loadPdf(props.url)
    pageCount.value = document_.pageCount
    await nextTick()
    observe()
  } catch (error) {
    toast.error(error)
  }
})

onBeforeUnmount(() => {
  observer?.disconnect()
  void document_?.destroy()
})

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

async function toggle(): Promise<void> {
  expanded.value = !expanded.value
  await nextTick()
  observe()
}
</script>

<template>
  <div ref="host" class="card flex flex-col gap-2 p-2">
    <div class="flex flex-wrap items-center gap-2 text-sm">
      <AppIcon name="file" />
      <span class="min-w-0 flex-1 truncate font-medium">{{ name }}</span>
      <span v-if="pageCount" class="text-slate-400">{{ $t('notes.pdf.pages', { count: pageCount }) }}</span>
      <button v-if="pageCount > 1" type="button" class="btn-secondary btn-small" @click="toggle">
        {{ expanded ? $t('notes.pdf.fewer') : $t('notes.pdf.all') }}
      </button>
      <a :href="url" target="_blank" rel="noopener" class="btn-secondary btn-small">
        <AppIcon name="external" />{{ $t('notes.pdf.open') }}
      </a>
    </div>
    <!-- Without the first page's canvas there is nothing to draw it on; the others follow on request. -->
    <canvas data-page="1" class="w-full rounded border border-slate-700 bg-white" />
    <template v-if="expanded">
      <canvas
        v-for="page in pageCount - 1"
        :key="page + 1"
        :data-page="page + 1"
        class="w-full rounded border border-slate-700 bg-white"
      />
    </template>
  </div>
</template>
