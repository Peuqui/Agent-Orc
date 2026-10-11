<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { HostStatus } from '../api'
import HostSessions from '../components/HostSessions.vue'
import QuotaPanel from '../components/QuotaPanel.vue'
import { useHosts } from '../composables/useHosts'
import { useToast } from '../composables/useToast'
import { useViewZoom } from '../composables/useViewZoom'

// The agents of all machines, this one's own first and each other machine below, set apart.
const { state, loadHosts, keepFresh } = useHosts()
const toast = useToast()
onMounted(() => loadHosts().catch(toast.error))
keepFresh()

// `host` is what the agents are asked of: null for this machine's own.
const machines = computed(() => [
  { name: state.value?.self ?? '', host: null, state: 'online' as HostStatus },
  ...(state.value?.hosts ?? []).map((other) => ({ name: other.name, host: other.name, state: other.state })),
])

// The views' font size scales what this page shows (see useViewZoom).
const zoomed = ref<HTMLElement>()
const { zoomStyle } = useViewZoom(zoomed)
</script>

<template>
  <section ref="zoomed" :style="zoomStyle">
    <!-- One for the account, whichever machine's agents are listed. -->
    <QuotaPanel class="mb-4" />
    <section v-for="(machine, index) in machines" :id="`host-${machine.name}`" :key="machine.name">
      <template v-if="machines.length > 1">
        <!-- A thin line that runs out to both ends by its opacity, with a glow that follows it (drop-shadow, so it shines in the middle only). -->
        <div
          v-if="index > 0"
          class="my-8 h-[1.5px] bg-[linear-gradient(90deg,transparent,#f59e0b_50%,transparent)] [filter:drop-shadow(0_0_4px_rgba(251,191,36,0.7))]"
          aria-hidden="true"
        />
        <div class="mb-3 flex items-center gap-2">
          <h2 class="text-sm font-semibold text-amber-400">{{ machine.name }}</h2>
          <span class="text-xs" :class="machine.state === 'online' ? 'text-emerald-400' : 'text-slate-500'">
            ● {{ $t(`hosts.short.${machine.state}`) }}
          </span>
        </div>
      </template>
      <HostSessions v-if="machine.state === 'online'" :host="machine.host" />
      <p v-else class="card p-4 text-sm text-slate-400">{{ $t(`hosts.reason.${machine.state}`) }}</p>
    </section>
  </section>
</template>
