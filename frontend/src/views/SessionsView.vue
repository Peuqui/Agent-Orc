<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { HostStatus } from '../api'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import HostSessions from '../components/HostSessions.vue'
import QuotaPanel from '../components/QuotaPanel.vue'
import { useHosts } from '../composables/useHosts'
import { useToast } from '../composables/useToast'
import { useViewZoom } from '../composables/useViewZoom'
import { api, ApiError, NETWORK_ERROR } from '../api'
import { POWER_PATIENCE_MS, powerButtons, type PowerAction, type PowerPermissions } from '../power'
import { offersWake, WAKE_PATIENCE_MS } from '../wake'

// The agents of all machines, this one's own first and each other machine below, set apart.
const { state, loadHosts, keepFresh } = useHosts()
const toast = useToast()
onMounted(() => loadHosts().catch(toast.error))
keepFresh()

// `host` is what the agents are asked of: null for this machine's own.
const machines = computed(() => [
  { name: state.value?.self ?? '', host: null, state: 'online' as HostStatus, canWake: false },
  ...(state.value?.hosts ?? []).map((other) => ({ name: other.name, host: other.name, state: other.state, canWake: other.can_wake })),
])

// The machines that were sent a wake-up packet and have not answered yet. The server tells when one
// does (keepFresh), so nothing polls; a machine that never comes up gets its button back after a while.
const waking = ref<string[]>([])
const { t } = useI18n()

function stopWaking(name: string): void {
  waking.value = waking.value.filter((other) => other !== name)
}

async function wake(name: string): Promise<void> {
  waking.value = [...waking.value, name]
  setTimeout(() => stopWaking(name), WAKE_PATIENCE_MS)
  try {
    await api.wakeHost(name)
  } catch (error) {
    stopWaking(name)
    toast.error(error)
  }
}

// What each reachable other machine allows to be done to it, asked of that machine itself (its own
// config decides). Asked once when it comes up; forgotten when it goes, so the next time asks again.
const permissions = ref<Record<string, PowerPermissions>>({})

async function learnPermissions(name: string): Promise<void> {
  try {
    permissions.value = { ...permissions.value, [name]: await api.hostPower(name) }
  } catch (error) {
    // A machine with an older Agent-Orc has no such endpoint: it just offers no buttons.
    console.error(`power permissions of ${name}`, error)
  }
}

// Per machine, the action that was sent and has not taken effect yet (the machine still answers).
const switching = ref<Record<string, PowerAction>>({})
// The action asked about in the dialog.
const asking = ref<{ name: string; action: PowerAction } | null>(null)

function stopSwitching(name: string): void {
  const { [name]: _gone, ...rest } = switching.value
  switching.value = rest
}

async function switchMachine(name: string, action: PowerAction): Promise<void> {
  asking.value = null
  switching.value = { ...switching.value, [name]: action }
  setTimeout(() => stopSwitching(name), POWER_PATIENCE_MS)
  try {
    await api.powerHost(name, action)
  } catch (error) {
    // The machine may go away before its answer arrives: that is what was asked, and the event
    // stream shows it. Any other answer (not allowed, polkit, an inhibitor) is a failure.
    const gone = error instanceof ApiError && (error.code === NETWORK_ERROR || error.status === 502)
    if (!gone) {
      stopSwitching(name)
      toast.error(error)
    }
  }
}

watch(state, (hosts) => {
  for (const host of hosts?.hosts ?? []) {
    if (host.state === 'online') {
      stopWaking(host.name)
      if (permissions.value[host.name] === undefined) void learnPermissions(host.name)
    } else {
      stopSwitching(host.name)
      const { [host.name]: _forgotten, ...rest } = permissions.value
      permissions.value = rest
    }
  }
})

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
          class="my-8 h-[1.5px] bg-[linear-gradient(90deg,transparent,var(--color-highlight-500)_50%,transparent)] [filter:drop-shadow(0_0_4px_color-mix(in_oklab,var(--color-highlight-400)_70%,transparent))]"
          aria-hidden="true"
        />
        <div class="mb-3 flex items-center gap-2">
          <h2 class="text-sm font-semibold text-highlight-400">{{ machine.name }}</h2>
          <span class="text-xs" :class="machine.state === 'online' ? 'text-ok-400' : 'text-muted'">
            ● {{ $t(`hosts.short.${machine.state}`) }}
          </span>
          <button
            v-for="action in powerButtons(machine, permissions[machine.name])"
            :key="action"
            class="btn-secondary btn-small"
            :disabled="machine.name in switching"
            @click="asking = { name: machine.name, action }"
          >
            {{ switching[machine.name] === action ? t(action === 'suspend' ? 'hosts.suspending' : 'hosts.poweringOff') : t(`hosts.${action}`) }}
          </button>
        </div>
      </template>
      <HostSessions v-if="machine.state === 'online'" :host="machine.host" />
      <div v-else class="card flex items-center justify-between gap-3 p-4 text-sm text-dim">
        <p>{{ $t(`hosts.reason.${machine.state}`) }}</p>
        <button
          v-if="offersWake(machine)"
          class="btn-secondary btn-small shrink-0"
          :disabled="waking.includes(machine.name)"
          @click="wake(machine.name)"
        >
          {{ waking.includes(machine.name) ? t('hosts.waking') : t('hosts.wake') }}
        </button>
      </div>
    </section>
    <ConfirmDialog
      v-if="asking"
      :title="$t(`hosts.${asking.action}`)"
      :message="$t(asking.action === 'suspend' ? 'hosts.confirmSuspend' : 'hosts.confirmPoweroff', { name: asking.name })"
      :confirm-label="$t(`hosts.${asking.action}`)"
      danger
      @confirm="switchMachine(asking.name, asking.action)"
      @close="asking = null"
    />
  </section>
</template>
