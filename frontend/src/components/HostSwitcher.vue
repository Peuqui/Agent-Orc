<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { currentHost, rootAddress } from '../api'
import { hostPath, sectionOf } from '../hostPaths'
import { fitLabel, textWidth } from '../labelFit'
import { NAV_ITEMS } from '../navigation'
import { useHosts } from '../composables/useHosts'
import { useToast } from '../composables/useToast'
import AppIcon from './AppIcon.vue'
import DropdownMenu from './DropdownMenu.vue'

// Which machine's agents the app shows: this one's or another's. A machine is a page of its own
// (its app, served below /hosts/<name>/), so changing it loads that page.
const { state, loadHosts, keepFresh } = useHosts()
const toast = useToast()
const { t } = useI18n()

const choosing = ref(false)
const trigger = ref<HTMLElement>()
// The machine's name on the button is cut to the width of this one (its full name is in the menu),
// so a long name does not push the other buttons out of a phone's header.
const WIDTH_OF = 'Mini'
const font = ref('')

onMounted(() => loadHosts().catch(toast.error))
keepFresh()

// The button exists once the machines are known. After the fonts are loaded: the letters' widths
// are those of the final font.
watch(trigger, async (button) => {
  if (!button) return
  await document.fonts.ready
  font.value = getComputedStyle(button).font
})

// The name this machine goes by here; the other machines are named in the config.
const own = computed(() => state.value?.self ?? '')
const chosen = computed(() => currentHost ?? own.value)
const shortName = computed(() =>
  font.value === '' ? chosen.value : fitLabel(chosen.value, textWidth(WIDTH_OF, font.value), font.value),
)
const choices = computed(() => [
  { name: own.value, label: own.value, up: true },
  ...(state.value?.hosts ?? []).map((host) => ({
    name: host.name,
    label: host.state === 'online' ? host.name : `${host.name} (${t(`hosts.short.${host.state}`)})`,
    up: host.state === 'online',
  })),
])

function choose(name: string): void {
  choosing.value = false
  const section = sectionOf(window.location.hash, NAV_ITEMS.map((item) => item.to), '/sessions')
  // The overview lists every machine: on it the choice leads to that machine's part.
  if (section === '/sessions' && currentHost === null) {
    document.getElementById(`host-${name}`)?.scrollIntoView({ behavior: 'smooth' })
    return
  }
  // From another machine's page "Agents" leads to the overview, which is this machine's own.
  const target =
    name === own.value || section === '/sessions'
      ? rootAddress()
      : hostPath(new URL(rootAddress()).pathname, name)
  // Stays in the section the page is in (a terminal, folder or workspace is one machine's own).
  window.location.assign(`${new URL(target, rootAddress()).href}#${section}`)
}
</script>

<template>
  <DropdownMenu v-if="state && state.hosts.length" v-model:open="choosing" right panel-class="flex w-44 flex-col p-1">
    <template #trigger="{ toggle }">
      <button
        ref="trigger"
        class="mr-1 flex h-6 items-center gap-0.5 rounded-md border border-highlight-500 bg-panel pr-0.5 pl-1.5 text-xs text-highlight-300"
        :aria-label="$t('hosts.machine')"
        :title="chosen"
        @click="toggle"
      >
        {{ shortName }}<AppIcon name="chevron" class="size-3.5" />
      </button>
    </template>
    <button
      v-for="choice in choices"
      :key="choice.name"
      class="rounded-md px-3 py-2 text-left text-sm hover:bg-raised disabled:text-muted disabled:hover:bg-transparent"
      :class="choice.name === chosen ? 'text-highlight-300' : 'text-soft'"
      :disabled="!choice.up"
      @click="choose(choice.name)"
    >
      {{ choice.label }}
    </button>
  </DropdownMenu>
</template>
