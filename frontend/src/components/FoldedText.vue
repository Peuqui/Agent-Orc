<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

// A message of the user in a limited number of lines, with "more" below where there is more to
// see (known by measuring, as line breaks of the screen are not those of the text).
const props = defineProps<{ text: string; lines: number }>()
const expanded = ref(false)
const overflowing = ref(false)
const box = ref<HTMLElement>()
const folded = computed(() => ({
  display: '-webkit-box',
  WebkitLineClamp: props.lines,
  WebkitBoxOrient: 'vertical' as const,
  overflow: 'hidden',
}))
const resizes = new ResizeObserver(measure)

function measure(): void {
  const element = box.value
  // Unfolded there is nothing cut off; the mark stays, to fold again.
  if (!element || expanded.value) return
  overflowing.value = element.scrollHeight > element.clientHeight + 1
}

onMounted(() => {
  measure()
  if (box.value) resizes.observe(box.value)
})
onBeforeUnmount(() => resizes.disconnect())
watch(() => [props.text, props.lines], measure, { flush: 'post' })
</script>

<template>
  <div>
    <p ref="box" class="break-words whitespace-pre-wrap" :style="expanded ? undefined : folded">{{ text }}</p>
    <button v-if="overflowing" type="button" class="mt-1 text-xs text-slate-500 underline" @click="expanded = !expanded">
      {{ expanded ? $t('answers.less') : $t('answers.more') }}
    </button>
  </div>
</template>
