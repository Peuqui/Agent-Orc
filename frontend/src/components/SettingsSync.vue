<script setup lang="ts">
import { rootAddress } from '../api'
import { loadSharedSettings } from '../composables/useSharedSettings'
import { useServerEvents } from '../composables/useServerEvents'
import { useToast } from '../composables/useToast'

// Keeps the shared settings (the server's, see useSharedSettings.ts) up to date: loads them as soon as the
// stream of the server's events is open, and again whenever another device changes one.
const toast = useToast()
// This machine's own app keeps them, also for another machine's page (api.ts).
useServerEvents(new URL('api/settings/events', rootAddress()).href, () => loadSharedSettings().catch(toast.error))
</script>

<template><span hidden /></template>
