<script setup lang="ts">
import { newVersion } from '../api'

async function reload(): Promise<void> {
  const registration = await navigator.serviceWorker?.getRegistration()
  await registration?.update()
  // A new service worker takes over and reloads the page by itself (registerType autoUpdate);
  // without a new one nothing cached stands in the way of a plain reload.
  if (!registration?.installing && !registration?.waiting) location.reload()
}
</script>

<template>
  <button
    v-if="newVersion"
    class="fixed inset-x-0 top-0 z-50 bg-red-700 px-4 py-2 text-center text-sm font-medium text-white"
    @click="reload"
  >
    {{ $t('app.newVersion') }}
  </button>
</template>
