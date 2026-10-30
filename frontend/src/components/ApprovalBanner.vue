<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useHosts } from '../composables/useHosts'
import { useToast } from '../composables/useToast'
import HostApprovals from './HostApprovals.vue'

// A request of an agent asks at the top of every page, whatever workspace is open and whichever
// machine the agent runs on, with the agent's name; a click on the name goes to that agent. Not for
// an agent in view: on its own page and in the columns of the open workspace the request shows at
// the input. Inside the workspace's iframes it would repeat once per column, so only the
// outermost page shows it.
const embedded = window.self !== window.top
const toast = useToast()
const { state, loadHosts, keepFresh } = useHosts()
onMounted(() => loadHosts().catch(toast.error))
keepFresh()

const hosts = computed<(string | null)[]>(() => [
  null,
  ...(state.value?.hosts.filter((host) => host.state === 'online').map((host) => host.name) ?? []),
])
</script>

<template>
  <div
    v-if="!embedded"
    class="pointer-events-none fixed inset-x-0 top-0 z-50 flex flex-col items-center gap-2 p-2 empty:hidden"
    aria-live="assertive"
  >
    <HostApprovals v-for="host in hosts" :key="host ?? ''" :host="host" />
  </div>
</template>
