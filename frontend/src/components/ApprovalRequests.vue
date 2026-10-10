<script setup lang="ts">
import { type AgentSession, type Approval } from '../api'
import AppIcon from './AppIcon.vue'
import { sessionName, useSessions } from '../composables/useSessions'
import { useApi } from '../composables/useHostContext'
import { useToast } from '../composables/useToast'

// named: shows whose request it is, with a button that goes to that agent (`open`) to see what it
// is about before deciding, for places away from it.
const props = defineProps<{ session: AgentSession; named?: boolean }>()
const emit = defineEmits<{ open: [] }>()

const { refresh } = useSessions()
const toast = useToast()
const api = useApi()

async function answer(approval: Approval, allow: boolean): Promise<void> {
  try {
    await api.answerApproval(props.session.id, approval.id, allow)
  } catch (error) {
    toast.error(error)
  }
  await refresh()
}
</script>

<template>
  <!-- The agent asks for a permission; the terminal asks too, the first answer counts. -->
  <div v-if="session.approvals.length" class="flex flex-col gap-2">
    <div
      v-for="approval in session.approvals"
      :key="approval.id"
      class="flex flex-col gap-2 rounded-lg border border-amber-600 bg-amber-950/40 px-3 py-2 text-sm"
    >
      <span v-if="named" class="font-semibold text-amber-100">{{ sessionName(session) }}</span>
      <span class="text-amber-200">
        {{ $t('approval.asks', { tool: approval.tool }) }}
        <span v-if="approval.description" class="text-amber-300/70"> · {{ approval.description }}</span>
      </span>
      <code class="line-clamp-3 rounded bg-slate-950/60 px-2 py-1 font-mono text-xs break-all text-slate-200">{{ approval.subject }}</code>
      <div class="flex gap-2">
        <button class="btn-primary btn-small" @click="answer(approval, true)">{{ $t('approval.allow') }}</button>
        <button class="btn-secondary btn-small" @click="answer(approval, false)">{{ $t('approval.deny') }}</button>
        <button
          v-if="named"
          type="button"
          class="btn-secondary btn-small ml-auto"
          :title="$t('approval.openAgent')"
          @click="emit('open')"
        >
          <AppIcon name="agents" />{{ $t('approval.goTo') }}
        </button>
      </div>
    </div>
  </div>
</template>
