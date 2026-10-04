<script setup lang="ts">
import { watch } from 'vue'
import { newVersion } from '../api'
import { reloadToNewVersion } from '../update'

// A newly installed version is taken at once (drafts in the input fields survive the reload,
// see MessageInput); the banner says what is happening. Inside the workspace's iframes it would
// repeat once per column, and reloading the outer page reloads them as well, so only the
// outermost page does it.
const embedded = window.self !== window.top

watch(newVersion, (available) => {
  if (available && !embedded) void reloadToNewVersion()
})
</script>

<template>
  <button
    v-if="newVersion && !embedded"
    class="fixed inset-x-0 top-0 z-50 bg-red-700 px-4 py-2 text-center text-sm font-medium text-white"
    @click="reloadToNewVersion"
  >
    {{ $t('app.newVersion') }}
  </button>
</template>
