<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { type AgentSession, type Approval } from '../api'
import { type PermissionSuggestion, suggestionText } from '../permissionSuggestions'
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
const { t } = useI18n()

/** Claude Code's offers to stop asking that the web app shows, with their index in the request. */
function offers(approval: Approval): { index: number; label: string; title: string }[] {
  return approval.suggestions.flatMap((suggestion: PermissionSuggestion, index) => {
    const text = suggestionText(suggestion)
    if (text === null) return []
    const what =
      text.kind === 'rules'
        ? text.text
        : text.kind === 'mode'
          ? t('approval.alwaysMode', { mode: t(`permission.modes.${text.mode}`) })
          : t('approval.alwaysDirectories', { what: text.text })
    const where = t(`approval.where.${suggestion.destination}`)
    return [{ index, label: t('approval.always', { what }), title: t('approval.alwaysTitle', { where }) }]
  })
}

async function answer(approval: Approval, allow: boolean, suggestion: number | null = null): Promise<void> {
  try {
    await api.answerApproval(props.session.id, approval.id, allow, suggestion)
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
      class="controls-zoom flex flex-col gap-2 rounded-lg border border-amber-600 bg-amber-950/40 px-3 py-2 text-sm"
    >
      <span v-if="named" class="font-semibold text-amber-100">{{ sessionName(session) }}</span>
      <span class="text-amber-200">
        {{ $t('approval.asks', { tool: approval.tool }) }}
        <span v-if="approval.description" class="text-amber-300/70"> · {{ approval.description }}</span>
      </span>
      <code class="line-clamp-3 rounded bg-slate-950/60 px-2 py-1 font-mono text-xs break-all text-slate-200">{{ approval.subject }}</code>
      <div class="flex flex-wrap gap-2">
        <button class="btn-primary btn-small" @click="answer(approval, true)">{{ $t('approval.allow') }}</button>
        <!-- As the terminal's "Yes, and don't ask again for ...": the rule Claude Code proposed, applied as it would. -->
        <button
          v-for="offer in offers(approval)"
          :key="offer.index"
          type="button"
          class="btn-secondary btn-small max-w-full text-left break-all"
          :title="offer.title"
          @click="answer(approval, true, offer.index)"
        >
          {{ offer.label }}
        </button>
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
