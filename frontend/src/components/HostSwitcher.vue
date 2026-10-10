<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { currentHost, rootAddress } from '../api'
import { hostPath, sectionOf } from '../hostPaths'
import { NAV_ITEMS } from '../navigation'
import { useHosts } from '../composables/useHosts'
import { useToast } from '../composables/useToast'

// Which machine's agents the app shows: this one's or another's. A machine is a page of its own
// (its app, served below /hosts/<name>/), so changing it loads that page.
const { state, loadHosts } = useHosts()
const toast = useToast()
const { t } = useI18n()

onMounted(() => loadHosts().catch(toast.error))

// The name this machine goes by here; the other machines are named in the config.
const own = computed(() => state.value?.self ?? '')
const chosen = computed(() => currentHost ?? own.value)
const choices = computed(() => [
  { name: own.value, label: own.value, up: true },
  ...(state.value?.hosts ?? []).map((host) => ({
    name: host.name,
    label: host.online ? host.name : t('hosts.offline', { name: host.name }),
    up: host.online,
  })),
])

function choose(name: string): void {
  const target = name === own.value ? rootAddress() : hostPath(new URL(rootAddress()).pathname, name)
  // Stays in the section the page is in (a terminal, folder or workspace is one machine's own).
  const section = sectionOf(window.location.hash, NAV_ITEMS.map((item) => item.to), '/sessions')
  window.location.assign(`${new URL(target, rootAddress()).href}#${section}`)
}
</script>

<template>
  <select
    v-if="state && state.hosts.length"
    class="mr-1 h-6 max-w-28 rounded-md border border-amber-500 bg-slate-800 px-1 text-xs text-amber-300"
    :aria-label="$t('hosts.machine')"
    :value="chosen"
    @change="choose(($event.target as HTMLSelectElement).value)"
  >
    <option v-for="choice in choices" :key="choice.name" :value="choice.name" :disabled="!choice.up">
      {{ choice.label }}
    </option>
  </select>
</template>
