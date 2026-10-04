<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type AgentSession, type Reasoning } from '../api'
import AppIcon from '../components/AppIcon.vue'
import BaseDialog from '../components/BaseDialog.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import ContextMeter from '../components/ContextMeter.vue'
import ReasoningControl from '../components/ReasoningControl.vue'
import QuotaPanel from '../components/QuotaPanel.vue'
import { moveInList, useReorder } from '../composables/useReorder'
import { useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import { baseName } from '../format'

const { sessions, profiles, refresh } = useSessions()
const toast = useToast()
const { t } = useI18n()
const stopping = ref<AgentSession | null>(null)
// A chosen reasoning waiting for confirmation; the control shows it until then.
const effortChange = ref<{ session: AgentSession; reasoning: Reasoning } | null>(null)

const levels = computed(() => new Map(profiles.value.map((p) => [p.name, p.effort_levels])))
const ultracodeOffered = computed(() => new Map(profiles.value.map((p) => [p.name, p.ultracode])))

// Cancelled: the slider falls back to the effort actually in effect.
function cancelEffort(): void {
  effortChange.value = null
}

/** "medium", "Standard + Ultracode", ... for the confirmation and pending notes. */
function reasoningLabel(reasoning: Reasoning): string {
  const effort = reasoning.effort ?? t('agent.effortDefault')
  return reasoning.ultracode ? `${effort} + ${t('agent.ultracode')}` : effort
}

function shownReasoning(session: AgentSession): Reasoning {
  return effortChange.value?.session.id === session.id
    ? effortChange.value.reasoning
    : { effort: session.effort, ultracode: session.ultracode }
}

function applyPendingNow(session: AgentSession): void {
  const pending = { effort: session.pending_effort, ultracode: session.pending_ultracode ?? false }
  void run(() => api.changeReasoning(session.id, pending, true))
}

function discardPending(session: AgentSession): void {
  void run(() => api.cancelEffortChange(session.id))
}

function applyEffort(immediately: boolean): void {
  const change = effortChange.value
  effortChange.value = null
  if (change) void run(() => api.changeReasoning(change.session.id, change.reasoning, immediately))
}

const labels = computed(() => new Map(profiles.value.map((p) => [p.name, p.label])))
// The user's arrangement (kept on the server); cards not arranged yet follow by name.
const cardOrder = ref<string[]>([])
api.cardOrder().then((order) => (cardOrder.value = order), toast.error)

function rank(session: AgentSession): number {
  const index = cardOrder.value.indexOf(session.path)
  return index === -1 ? Number.MAX_SAFE_INTEGER : index
}

const sorted = computed(() =>
  [...sessions.value].sort(
    (a, b) => rank(a) - rank(b) || baseName(a.path).localeCompare(baseName(b.path)),
  ),
)

// A card is dragged at a free spot (mouse) or after holding it (finger) and takes the place of
// the card it is dropped on.
const reorder = useReorder({
  targetAt: (x, y) =>
    document
      .elementsFromPoint(x, y)
      .map((element) => element.closest<HTMLElement>('[data-card]')?.dataset.card)
      .find((folder) => folder !== undefined) ?? null,
  onDrop: (folder, target) => {
    const folders = sorted.value.map((session) => session.path)
    moveInList(folders, folder, target)
    cardOrder.value = folders
    void run(() => api.arrangeCards(folders))
  },
  ignore: 'button, a, input, [role="switch"]',
})
const drag = reorder.drag

// Named workspaces, opened again with one tap; the unnamed one of a browser tab is not listed.
const workspaceNames = ref<string[]>([])
const deletingWorkspace = ref<string | null>(null)

function loadWorkspaceNames(): void {
  api.workspaces().then((named) => (workspaceNames.value = Object.keys(named).sort()), toast.error)
}

loadWorkspaceNames()

function confirmDeleteWorkspace(): void {
  const workspace = deletingWorkspace.value
  deletingWorkspace.value = null
  if (workspace !== null) api.deleteWorkspace(workspace).then(loadWorkspaceNames, toast.error)
}

async function run(action: () => Promise<unknown>): Promise<void> {
  try {
    await action()
  } catch (error) {
    toast.error(error)
  }
  await refresh()
}

function confirmStop(): void {
  const session = stopping.value
  stopping.value = null
  if (session) void run(() => api.stopSession(session.id))
}

function resume(session: AgentSession): void {
  // Resume with the effort the agent last reported.
  void run(() =>
    api.startSession(session.profile, session.path, true, {
      effort: session.effort,
      ultracode: session.ultracode,
    }),
  )
}
</script>

<template>
  <section>
    <!-- Always reachable: a new agent starts in a folder chosen in the file view. -->
    <QuotaPanel />
    <RouterLink to="/files" class="btn-primary mb-4 w-full sm:w-auto">
      <AppIcon name="plus" />{{ $t('sessions.startNew') }}
    </RouterLink>
    <div v-if="workspaceNames.length > 0" class="mb-4 flex flex-wrap items-center gap-2">
      <span class="text-sm text-slate-400">{{ $t('workspace.saved') }}</span>
      <span v-for="workspace in workspaceNames" :key="workspace" class="card flex items-center">
        <RouterLink
          :to="{ path: '/workspace', query: { name: workspace } }"
          class="flex items-center gap-1.5 py-1 pl-3 text-sm hover:text-slate-100"
        >
          <AppIcon name="workspace" />{{ workspace }}
        </RouterLink>
        <button
          class="px-2.5 py-1 text-slate-500 hover:text-slate-200"
          :aria-label="$t('workspace.delete')"
          :title="$t('workspace.delete')"
          @click="deletingWorkspace = workspace"
        >
          ×
        </button>
      </span>
    </div>
    <p v-if="sorted.length === 0" class="card p-6 text-center text-slate-400">{{ $t('sessions.empty') }}</p>

    <!-- As many cards side by side as fit, before the page has to scroll; one column on phones.
         Below 24rem the row with context, effort and ultracode would wrap. -->
    <ul class="grid grid-cols-[repeat(auto-fill,minmax(min(24rem,100%),1fr))] gap-3">
      <li
        v-for="session in sorted"
        :key="session.id"
        :data-card="session.path"
        class="card flex touch-pan-y flex-col gap-2 px-4 py-3 select-none [-webkit-touch-callout:none]"
        :class="[
          drag?.active && drag.target === session.path && drag.id !== session.path ? 'ring-2 ring-amber-400' : '',
          drag?.active && drag.id === session.path ? 'opacity-50' : '',
        ]"
        @pointerdown="reorder.onPointerDown($event, session.path)"
        @pointermove="reorder.onPointerMove"
        @pointerup="reorder.onPointerUp"
        @pointercancel="reorder.cancel"
        @touchmove="reorder.onTouchMove"
        @contextmenu="drag?.active && $event.preventDefault()"
      >
        <div class="flex items-center gap-3">
          <div class="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-3">
            <h2 class="font-semibold">{{ baseName(session.path) }}</h2>
            <span class="min-w-0 truncate text-xs text-slate-500">{{ session.path }}</span>
            <span class="text-sm text-slate-400">
              {{ labels.get(session.profile) ?? session.profile }}
              <span v-if="session.model" class="text-slate-500"> · {{ session.model }}</span>
            </span>
          </div>
          <span
            v-if="session.running && session.busy"
            class="shrink-0 animate-pulse rounded-full bg-amber-900/40 px-2.5 py-0.5 text-xs font-medium text-amber-300"
          >
            {{ $t('sessions.working') }}
          </span>
          <span
            v-else
            class="shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium"
            :class="session.running ? 'bg-red-900/40 text-red-300' : 'bg-slate-700 text-slate-300'"
          >
            {{
              session.running
                ? $t('sessions.running')
                : session.exit_status === null
                  ? $t('sessions.ended')
                  : $t('sessions.exited', { code: session.exit_status })
            }}
          </span>
        </div>
        <div class="flex items-center gap-x-3">
          <ContextMeter
            v-if="session.context_tokens != null && session.context_window != null"
            :tokens="session.context_tokens"
            :window="session.context_window"
          />
          <ReasoningControl
            v-if="session.running && levels.get(session.profile)?.length"
            class="min-w-0 flex-1"
            compact
            :levels="levels.get(session.profile) ?? []"
            :ultracode-offered="ultracodeOffered.get(session.profile) ?? false"
            :model-value="shownReasoning(session)"
            :disabled="session.effort_pending"
            @update:model-value="(reasoning) => (effortChange = { session, reasoning })"
          />
        </div>
        <div
          v-if="session.effort_pending"
          class="flex flex-wrap items-center gap-2 rounded-lg border border-amber-700 bg-amber-950/40 px-3 py-2 text-sm text-amber-200"
        >
          <span class="flex-1">
            {{
              $t('sessions.effortPending', {
                effort: reasoningLabel({
                  effort: session.pending_effort,
                  ultracode: session.pending_ultracode ?? false,
                }),
              })
            }}
          </span>
          <button
            class="btn-secondary min-h-9"
            @click="applyPendingNow(session)"
          >
            {{ $t('sessions.applyNow') }}
          </button>
          <button class="btn min-h-9" @click="discardPending(session)">
            {{ $t('sessions.discard') }}
          </button>
        </div>
        <div class="flex flex-wrap gap-2">
          <RouterLink
            v-if="session.running"
            :to="{ path: '/workspace', query: { open: session.id } }"
            class="btn-primary btn-small"
          >
            <AppIcon name="agents" />{{ $t('sessions.terminal') }}
          </RouterLink>
          <button v-if="!session.running" class="btn-primary btn-small" @click="resume(session)">
            <AppIcon name="resume" />{{ $t('sessions.resume') }}
          </button>
          <button class="btn-secondary btn-small" @click="stopping = session">
            <AppIcon name="stop" />{{ $t('sessions.stop') }}
          </button>
        </div>
      </li>
    </ul>

    <BaseDialog v-if="effortChange" :title="$t('agent.effort')" @close="cancelEffort">
      <p class="mb-5 text-slate-300">
        {{
          $t(effortChange.session.busy ? 'sessions.confirmEffortBusy' : 'sessions.confirmEffort', {
            name: baseName(effortChange.session.path),
            effort: reasoningLabel(effortChange.reasoning),
          })
        }}
      </p>
      <div class="flex flex-col gap-2">
        <template v-if="effortChange.session.busy">
          <button class="btn-primary" @click="applyEffort(false)">{{ $t('sessions.changeAfterAnswer') }}</button>
          <button class="btn-danger" @click="applyEffort(true)">{{ $t('sessions.changeNow') }}</button>
        </template>
        <button v-else class="btn-primary" @click="applyEffort(false)">{{ $t('sessions.changeEffort') }}</button>
        <button class="btn" @click="cancelEffort">{{ $t('common.cancel') }}</button>
      </div>
    </BaseDialog>
    <ConfirmDialog
      v-if="stopping"
      :title="$t('sessions.stop')"
      :message="$t('sessions.confirmStop', { name: baseName(stopping.path) })"
      :confirm-label="$t('sessions.stop')"
      danger
      @confirm="confirmStop"
      @close="stopping = null"
    />
    <ConfirmDialog
      v-if="deletingWorkspace"
      :title="$t('workspace.delete')"
      :message="$t('workspace.confirmDelete', { name: deletingWorkspace })"
      :confirm-label="$t('workspace.delete')"
      danger
      @confirm="confirmDeleteWorkspace"
      @close="deletingWorkspace = null"
    />
  </section>
</template>
