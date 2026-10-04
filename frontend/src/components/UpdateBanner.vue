<script setup lang="ts">
import { newVersion } from '../api'
import { reloadToNewVersion } from '../update'

// Inside the workspace's iframes the banner would repeat once per column; reloading the outer
// page reloads them as well, so only the outermost page shows it.
const embedded = window.self !== window.top
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
