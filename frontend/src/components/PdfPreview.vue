<script setup lang="ts">
import { ref } from 'vue'
import AppIcon from './AppIcon.vue'
import PdfPages from './PdfPages.vue'

// A PDF of a note: the first page as a preview, on request all pages one below the other.
defineProps<{ url: string; name: string }>()
const pageCount = ref(0)
const expanded = ref(false)
</script>

<template>
  <div class="card flex flex-col gap-2 p-2">
    <div class="flex flex-wrap items-center gap-2 text-sm">
      <AppIcon name="file" />
      <span class="min-w-0 flex-1 truncate font-medium">{{ name }}</span>
      <span v-if="pageCount" class="text-dim">{{ $t('notes.pdf.pages', { count: pageCount }) }}</span>
      <button v-if="pageCount > 1" type="button" class="btn-secondary btn-small" @click="expanded = !expanded">
        {{ expanded ? $t('notes.pdf.fewer') : $t('notes.pdf.all') }}
      </button>
      <a :href="url" target="_blank" rel="noopener" class="btn-secondary btn-small">
        <AppIcon name="external" />{{ $t('notes.pdf.open') }}
      </a>
    </div>
    <PdfPages :url="url" :all="expanded" @loaded="(count) => (pageCount = count)" />
  </div>
</template>
