<script setup lang="ts">
// The pictures of a message as small tiles in a row, each opening at full size in a tab of its own.
defineProps<{ urls: string[] }>()

function open(address: string): void {
  window.open(address, '_blank', 'noopener')
}
</script>

<template>
  <div v-if="urls.length" class="mt-2 flex flex-row flex-wrap gap-2">
    <img
      v-for="url in urls"
      :key="url"
      :src="url"
      :alt="$t('answers.picture')"
      loading="lazy"
      class="h-20 w-28 shrink-0 cursor-zoom-in rounded border border-slate-600 object-cover"
      @click="open(url)"
    />
  </div>
</template>
