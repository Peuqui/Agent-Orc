<script setup lang="ts">
import { ref } from 'vue'
import type { AgentSession } from '../api'
import { sessionName } from '../composables/useSessions'
import AppIcon from './AppIcon.vue'
import DropdownMenu from './DropdownMenu.vue'

// The "+" of a workspace: the running agents not open here (one from another workspace moves
// here), or starting a new one.
defineProps<{
  candidates: { session: AgentSession; livesIn: string | null }[]
}>()
const emit = defineEmits<{ open: [id: string] }>()
const picking = ref(false)

function pick(id: string): void {
  picking.value = false
  emit('open', id)
}
</script>

<template>
  <DropdownMenu v-model:open="picking" right panel-class="flex w-64 flex-col gap-1 p-2">
    <template #trigger="{ toggle }">
      <button
        class="flex size-8 items-center justify-center rounded-md border border-slate-600 text-slate-300 hover:bg-slate-700"
        :aria-label="$t('workspace.add')"
        :title="$t('workspace.add')"
        @click="toggle"
      >
        <AppIcon name="plus" class="size-4" />
      </button>
    </template>
    <button
      v-for="{ session, livesIn } in candidates"
      :key="session.id"
      class="rounded-md px-3 py-2 text-left hover:bg-slate-700"
      @click="pick(session.id)"
    >
      {{ sessionName(session) }}
      <span v-if="livesIn" class="text-xs text-slate-500"> · {{ $t('workspace.movesFrom', { name: livesIn }) }}</span>
    </button>
    <p v-if="candidates.length === 0" class="px-3 py-2 text-sm text-slate-500">{{ $t('workspace.allOpen') }}</p>
    <RouterLink :to="{ path: '/files', query: { workspace: '1' } }" class="btn-primary mt-1">
      <AppIcon name="plus" />{{ $t('sessions.startNew') }}
    </RouterLink>
  </DropdownMenu>
</template>
