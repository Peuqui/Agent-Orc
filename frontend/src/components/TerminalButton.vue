<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import AppIcon from './AppIcon.vue'

// ">_": a plain terminal in the folder, next to its agent; opens the running one if there is.
// What is started in it is the user's business (no second agent in the same folder).
const props = defineProps<{ path: string; buttonClass: string }>()
const router = useRouter()
const toast = useToast()
const { terminalByPath, terminalProfile, refresh } = useSessions()
const running = computed(() => terminalByPath.value.get(props.path))

async function open(): Promise<void> {
  if (!terminalProfile.value) return
  try {
    const terminal = running.value?.running
      ? running.value
      : await api.startSession(terminalProfile.value.name, props.path, false, {
          effort: null,
          ultracode: false,
        })
    await refresh()
    // In a workspace column, the router hands this to the tab's workspace.
    await router.push({ path: '/workspace', query: { open: terminal.id } })
  } catch (error) {
    toast.error(error)
  }
}
</script>

<template>
  <button
    v-if="terminalProfile"
    :class="buttonClass"
    :title="$t('terminalButton.title')"
    :aria-label="$t('terminalButton.title')"
    @click="open"
  >
    <AppIcon name="prompt" />
  </button>
</template>
