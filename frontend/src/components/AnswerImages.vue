<script setup lang="ts">
import { ref } from 'vue'
import AppIcon from './AppIcon.vue'

// The pictures of a message: a small mark with their number, which unfolds them as tiles in a
// row (each opening at full size in a tab of its own) and folds them again.
defineProps<{ urls: string[] }>()
const open = ref(false)

function openPicture(address: string): void {
  window.open(address, '_blank', 'noopener')
}
</script>

<template>
  <div v-if="urls.length" class="mt-2 flex flex-col gap-2">
    <button
      type="button"
      class="flex w-fit items-center gap-1.5 rounded-md border border-slate-600 px-2 py-0.5 text-xs text-slate-300 hover:bg-slate-700"
      :aria-expanded="open"
      @click="open = !open"
    >
      <AppIcon name="image" class="size-3.5" />{{ $t('answers.pictures', { count: urls.length }, urls.length) }}
    </button>
    <div v-if="open" class="flex flex-row flex-wrap gap-2">
      <img
        v-for="url in urls"
        :key="url"
        :src="url"
        :alt="$t('answers.picture')"
        loading="lazy"
        class="h-20 w-28 shrink-0 cursor-zoom-in rounded border border-slate-600 object-cover"
        @click="openPicture(url)"
      />
    </div>
  </div>
</template>
