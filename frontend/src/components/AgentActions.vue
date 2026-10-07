<script setup lang="ts">
import { computed } from 'vue'
import type { AgentSession } from '../api'
import { useSessions } from '../composables/useSessions'
import AppIcon from './AppIcon.vue'
import ContextButton from './ContextButton.vue'
import RestartButton from './RestartButton.vue'
import ScheduleButton from './ScheduleButton.vue'

// What is done to a running agent, less often than looking at it (and partly with consequences):
// the content of the ⋮ menu on the card and in the agent's page. The last item stops the agent.
const props = defineProps<{ session: AgentSession }>()
// done: an action's dialog is over, so the menu holding these items can close.
const emit = defineEmits<{ stop: []; done: [] }>()
const { profiles } = useSessions()
const itemClass =
  'flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-slate-300 hover:bg-slate-700 disabled:opacity-40'
const profile = computed(() => profiles.value.find((p) => p.name === props.session.profile))
// There is something to change: models to choose from, or another agent to switch to.
const canChange = computed(
  () =>
    profile.value?.models === true ||
    profiles.value.some((p) => p.terminal === profile.value?.terminal && p.name !== profile.value?.name),
)
</script>

<template>
  <ScheduleButton :session="session" :button-class="itemClass" with-label @done="emit('done')" />
  <RestartButton v-if="canChange" change-model :session="session" :button-class="itemClass" with-label @done="emit('done')" />
  <ContextButton
    v-for="action in profile?.context_actions ?? []"
    :key="action"
    :session="session"
    :action="action"
    :button-class="itemClass"
    with-label
    @done="emit('done')"
  />
  <RestartButton :session="session" :button-class="itemClass" with-label @done="emit('done')" />
  <hr class="my-1 border-slate-700" />
  <button :class="`${itemClass} !text-red-400`" @click="emit('stop')">
    <AppIcon name="stop" />{{ $t('sessions.stop') }}
  </button>
</template>
