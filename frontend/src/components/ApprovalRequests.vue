<script setup lang="ts">
import { reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { type AgentSession, type Approval, type ApprovalAnswer } from '../api'
import { renderMarkdown } from '../markdown'
import { type PermissionSuggestion, suggestionText } from '../permissionSuggestions'
import { APPROVAL_ATTRIBUTE, APPROVAL_FIRST_ATTRIBUTE } from '../columns'
import AppIcon from './AppIcon.vue'
import { sessionName, useSessions } from '../composables/useSessions'
import { useApi } from '../composables/useHostContext'
import { useToast } from '../composables/useToast'

// named: shows whose request it is, with a button that goes to that agent (`open`) to see what it
// is about before deciding, for places away from it. hostName: another machine's agent, which
// says whose it is.
const props = defineProps<{ session: AgentSession; named?: boolean; hostName?: string | null }>()
// leave: Escape on the request, to go back to typing without deciding.
const emit = defineEmits<{ open: []; leave: [] }>()

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

// What Claude should do instead, typed per request; sent with a denial, as the terminal's "No, and
// tell Claude what to do differently". A denial without it stops Claude, as Esc does.
const instead = reactive<Record<string, string>>({})

function insteadOf(approval: Approval): string {
  return (instead[approval.id] ?? '').trim()
}

function deny(approval: Approval): Promise<void> {
  const message = insteadOf(approval)
  return answer(approval, message ? { allow: false, message } : { allow: false })
}

function denyLabel(approval: Approval): string {
  if (!insteadOf(approval)) return t('approval.stop')
  return approval.plan === null ? t('approval.sendInstead') : t('approval.keepPlanning')
}

async function answer(approval: Approval, decision: ApprovalAnswer): Promise<void> {
  try {
    await api.answerApproval(props.session.id, approval.id, decision)
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
      class="controls-zoom flex flex-col gap-2 rounded-lg border border-highlight-500 bg-highlight-950/40 px-3 py-2 text-sm"
      v-bind="{ [APPROVAL_ATTRIBUTE]: '' }"
      @keydown.esc="emit('leave')"
    >
      <span v-if="named" class="font-semibold text-highlight-200">
        {{ sessionName(session) }}<span v-if="hostName" class="font-normal"> · {{ hostName }}</span>
      </span>
      <template v-if="approval.plan !== null">
        <span class="text-highlight-200">{{ $t('approval.plan') }}</span>
        <div class="markdown note max-h-72 overflow-y-auto rounded bg-sunken/60 px-2 py-1 select-text" v-html="renderMarkdown(approval.plan, null)" />
      </template>
      <template v-else>
        <span class="text-highlight-200">
          {{ $t('approval.asks', { tool: approval.tool }) }}
          <span v-if="approval.description" class="text-highlight-300/70"> · {{ approval.description }}</span>
        </span>
        <code class="line-clamp-3 rounded bg-sunken/60 px-2 py-1 font-mono text-xs break-all text-main">{{ approval.subject }}</code>
      </template>
      <div class="flex flex-wrap gap-2">
        <!-- A plan goes ahead in one of the modes the agent may run in, as the terminal offers them. -->
        <template v-if="approval.plan !== null">
          <button
            v-for="(mode, index) in approval.modes"
            :key="mode"
            type="button"
            class="btn-primary btn-small"
            v-bind="index === 0 ? { [APPROVAL_FIRST_ATTRIBUTE]: '' } : {}"
            @click="answer(approval, { allow: true, mode })"
          >
            {{ $t('approval.approvePlan', { mode: $t(`permission.modes.${mode}`) }) }}
          </button>
        </template>
        <template v-else>
          <button class="btn-primary btn-small" v-bind="{ [APPROVAL_FIRST_ATTRIBUTE]: '' }" @click="answer(approval, { allow: true })">
            {{ $t('approval.allow') }}
          </button>
          <!-- As the terminal's "Yes, and don't ask again for ...": the rule Claude Code proposed, applied as it would. -->
          <button
            v-for="offer in offers(approval)"
            :key="offer.index"
            type="button"
            class="btn-secondary btn-small max-w-full text-left break-all"
            :title="offer.title"
            @click="answer(approval, { allow: true, suggestion: offer.index })"
          >
            {{ offer.label }}
          </button>
        </template>
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
      <form class="flex gap-2" @submit.prevent="deny(approval)">
        <input
          v-model="instead[approval.id]"
          class="input min-w-0 flex-1 py-1 text-sm"
          :placeholder="approval.plan === null ? $t('approval.insteadHint') : $t('approval.changeHint')"
          enterkeyhint="send"
        />
        <button type="submit" class="btn-secondary btn-small" :title="insteadOf(approval) ? undefined : $t('approval.stopTitle')">
          {{ denyLabel(approval) }}
        </button>
      </form>
    </div>
  </div>
</template>
