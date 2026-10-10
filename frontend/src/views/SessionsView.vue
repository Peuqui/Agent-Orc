<script setup lang="ts">
import { computed, onMounted } from 'vue'
import HostSessions from '../components/HostSessions.vue'
import QuotaPanel from '../components/QuotaPanel.vue'
import { useHosts } from '../composables/useHosts'
import { useToast } from '../composables/useToast'

// The agents of all machines, this one's own first and each other machine below, set apart.
const { state, loadHosts, keepFresh } = useHosts()
const toast = useToast()
onMounted(() => loadHosts().catch(toast.error))
keepFresh()

// `host` is what the agents are asked of: null for this machine's own.
const machines = computed(() => [
  { name: state.value?.self ?? '', host: null, online: true },
  ...(state.value?.hosts ?? []).map((other) => ({ name: other.name, host: other.name, online: other.online })),
])
</script>

<template>
  <section>
    <!-- One for the account, whichever machine's agents are listed. -->
    <QuotaPanel class="mb-4" />
    <section v-for="(machine, index) in machines" :id="`host-${machine.name}`" :key="machine.name">
      <template v-if="machines.length > 1">
        <hr v-if="index > 0" class="my-6 border-slate-700" />
        <div class="mb-3 flex items-center gap-2">
          <h2 class="text-sm font-semibold text-amber-400">{{ machine.name }}</h2>
          <span class="text-xs" :class="machine.online ? 'text-emerald-400' : 'text-slate-500'">
            ● {{ machine.online ? $t('hosts.online') : $t('hosts.offlineShort') }}
          </span>
        </div>
      </template>
      <HostSessions v-if="machine.online" :host="machine.host" />
      <p v-else class="card p-4 text-sm text-slate-400">{{ $t('hosts.unreachable') }}</p>
    </section>
  </section>
</template>
