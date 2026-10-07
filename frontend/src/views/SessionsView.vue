<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { api, type AgentSession, type Reasoning, type WorkspaceSet } from '../api'
import AppIcon from '../components/AppIcon.vue'
import BaseDialog from '../components/BaseDialog.vue'
import BroadcastButton from '../components/BroadcastButton.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import ModelDialog from '../components/ModelDialog.vue'
import ContextMeter from '../components/ContextMeter.vue'
import ReasoningControl from '../components/ReasoningControl.vue'
import QuotaPanel from '../components/QuotaPanel.vue'
import AgentActions from '../components/AgentActions.vue'
import ApprovalRequests from '../components/ApprovalRequests.vue'
import DropdownMenu from '../components/DropdownMenu.vue'
import TerminalButton from '../components/TerminalButton.vue'
import ScheduledList from '../components/ScheduledList.vue'
import { moveInList, useReorder } from '../composables/useReorder'
import { cardKey, sessionName, useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import { useWorkspaceChanges } from '../composables/useWorkspaceChanges'
import { agentRoute, homeOf, openWorkspace, unnamedListed, useOtherTabs } from '../composables/useWorkspaceTab'

const { sessions, profiles, refresh } = useSessions()
const toast = useToast()
const router = useRouter()
const { t, te } = useI18n()
const stopping = ref<AgentSession | null>(null)
// A chosen reasoning waiting for confirmation; the control shows it until then.
const effortChange = ref<{ session: AgentSession; reasoning: Reasoning } | null>(null)

const permissionModes = computed(() => new Map(profiles.value.map((p) => [p.name, p.permission_modes])))
const effortLive = computed(() => new Map(profiles.value.map((p) => [p.name, p.effort_live])))
const ultracodeOffered = computed(() => new Map(profiles.value.map((p) => [p.name, p.ultracode])))

// Cancelled: the slider falls back to the effort actually in effect.
function cancelEffort(): void {
  effortChange.value = null
}

/** "medium", "Standard + Ultracode", ... for the confirmation and pending notes. */
function reasoningLabel(reasoning: Reasoning): string {
  const effort = reasoning.effort ?? ''
  return reasoning.ultracode ? `${effort} + ${t('agent.ultracode')}` : effort
}

function shownReasoning(session: AgentSession): Reasoning {
  return effortChange.value?.session.id === session.id
    ? effortChange.value.reasoning
    : { effort: session.effort, ultracode: session.ultracode }
}

/** The confirmation names what really happens: a switch in place, or a restart. */
function effortMessage(session: AgentSession): string {
  if (effortLive.value.get(session.profile)) {
    return session.busy ? 'sessions.confirmEffortLiveBusy' : 'sessions.confirmEffortLive'
  }
  return session.busy ? 'sessions.confirmEffortBusy' : 'sessions.confirmEffort'
}

function applyPendingNow(session: AgentSession): void {
  const pending = { effort: session.pending_effort, ultracode: session.pending_ultracode ?? false }
  void run(() => api.changeReasoning(session.id, pending, true))
}

function discardPending(session: AgentSession): void {
  void run(() => api.cancelEffortChange(session.id))
}

function discardPendingModel(session: AgentSession): void {
  void run(() => api.cancelModelChange(session.id))
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
  const index = cardOrder.value.indexOf(cardKey(session))
  return index === -1 ? Number.MAX_SAFE_INTEGER : index
}

const sorted = computed(() =>
  [...sessions.value].sort(
    (a, b) => rank(a) - rank(b) || sessionName(a).localeCompare(sessionName(b)),
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
    const folders = sorted.value.map(cardKey)
    moveInList(folders, folder, target)
    cardOrder.value = folders
    void run(() => api.arrangeCards(folders))
  },
  ignore: 'button, a, input, select, [role="switch"]',
})
const drag = reorder.drag

// Named workspaces, opened again with one tap; the unnamed one has a button of its own.
const workspaces = ref<WorkspaceSet | null>(null)
const workspaceNames = computed(() => Object.keys(workspaces.value?.named ?? {}).sort())
// The unnamed workspace is listed while it holds agents or is the only one; otherwise "+" starts one.
const showUnnamed = computed(
  () =>
    workspaces.value !== null &&
    unnamedListed(workspaceNames.value.length, workspaces.value.unnamed.tabs.length, false),
)
const deletingWorkspace = ref<string | null>(null)
const removingWorktree = ref<AgentSession | null>(null)

function confirmRemoveWorktree(): void {
  const session = removingWorktree.value
  removingWorktree.value = null
  if (!session) return
  void run(async () => {
    const removal = await api.removeWorktree(session.id)
    toast.info(t(removal.branch_deleted ? 'worktree.removedWithBranch' : 'worktree.removedKeptBranch', { branch: removal.branch }))
  })
}
const otherTabs = useOtherTabs()

function loadWorkspaces(): void {
  api.workspaces().then((everything) => (workspaces.value = everything), toast.error)
}

// Loads once the stream connects, and again whenever a workspace changed on any device.
useWorkspaceChanges(loadWorkspaces)

const terminalRoute = (agent: string) => agentRoute(workspaces.value, agent)

/** The agent's workspace as the selection's value: "" is the unnamed one. */
function workspaceOf(agent: string): string {
  return (workspaces.value ? homeOf(workspaces.value, agent) : null) ?? ''
}

function moveToWorkspace(session: AgentSession, workspace: string): void {
  void run(() => api.moveSession(session.id, workspace))
}

function confirmDeleteWorkspace(): void {
  const workspace = deletingWorkspace.value
  deletingWorkspace.value = null
  if (workspace !== null) api.deleteWorkspace(workspace).then(loadWorkspaces, toast.error)
}

/** Known modes by name; a mode added in the config shows as it is written there. */
function permissionLabel(mode: string): string {
  return te(`permission.modes.${mode}`) ? t(`permission.modes.${mode}`) : mode
}

function contextPercent(session: AgentSession): number {
  if (session.context_tokens == null || !session.context_window) return 0
  return Math.round((session.context_tokens / session.context_window) * 100)
}

function requestHandover(session: AgentSession): void {
  void run(() => api.requestHandover(session.id))
}

function changePermissionMode(session: AgentSession, mode: string): void {
  void run(async () => {
    await api.changePermissionMode(session.id, mode)
    if (session.running) toast.info(t('permission.changed', { name: sessionName(session) }))
  })
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

const modelProfiles = computed(() => new Set(profiles.value.filter((p) => p.models).map((p) => p.name)))
// An ended agent that offers models but has none stored: resumed once a model is chosen.
const resumingWithoutModel = ref<AgentSession | null>(null)

function resume(session: AgentSession): void {
  if (session.chosen_model === null && modelProfiles.value.has(session.profile)) {
    resumingWithoutModel.value = session
    return
  }
  // The model it was started with, and the effort the agent last reported (a model without
  // levels gets none, whatever the agent reports).
  resumeWith(session, session.chosen_model, session.effort_levels.length ? session.effort : null)
}

function resumeWith(session: AgentSession, model: string | null, effort: string | null): void {
  resumingWithoutModel.value = null
  void run(() =>
    api.startSession(session.profile, session.path, true, { effort, ultracode: session.ultracode }, null, null, model),
  )
}
</script>

<template>
  <section>
    <!-- Always reachable: a new agent starts in a folder chosen in the file view. -->
    <QuotaPanel />
    <!-- Named workspaces next to it: a tap opens one (its own browser tab once this one shows
         agents); the link address lets a middle click open a tab, too. -->
    <div class="mb-4 flex flex-wrap items-center gap-2">
      <RouterLink to="/files" class="btn-primary w-full sm:w-auto">
        <AppIcon name="plus" />{{ $t('sessions.startNew') }}
      </RouterLink>
      <button v-if="showUnnamed" class="btn-secondary btn-small" @click="openWorkspace(router, null)">
        <AppIcon name="workspace" />{{ $t('workspace.unnamed') }}
      </button>
      <span v-for="workspace in workspaceNames" :key="workspace" class="card flex items-center">
        <a
          :href="router.resolve({ path: '/workspace', query: { name: workspace } }).href"
          class="flex items-center gap-1.5 py-1.5 pl-3 text-sm hover:text-slate-100"
          :title="otherTabs.has(workspace) ? $t('workspace.openElsewhere') : undefined"
          @click.prevent="openWorkspace(router, workspace)"
        >
          <AppIcon name="workspace" />{{ workspace }}
          <AppIcon v-if="otherTabs.has(workspace)" name="external" class="size-3.5 text-slate-500" />
        </a>
        <button
          class="px-2.5 py-1.5 text-slate-500 hover:text-slate-200"
          :aria-label="$t('workspace.delete')"
          :title="$t('workspace.delete')"
          @click="deletingWorkspace = workspace"
        >
          ×
        </button>
      </span>
      <button
        v-if="workspaces !== null && !showUnnamed"
        class="btn-secondary btn-small"
        @click="openWorkspace(router, null)"
      >
        <AppIcon name="plus" />{{ $t('workspace.new') }}
      </button>
      <BroadcastButton />
    </div>
    <p v-if="sorted.length === 0" class="card p-6 text-center text-slate-400">{{ $t('sessions.empty') }}</p>

    <!-- As many cards side by side as fit, before the page has to scroll; one column on phones.
         Below 24rem the row with context, effort and ultracode would wrap. -->
    <ul class="grid grid-cols-[repeat(auto-fill,minmax(min(24rem,100%),1fr))] gap-3">
      <li
        v-for="session in sorted"
        :key="session.id"
        :data-card="cardKey(session)"
        class="card flex touch-pan-y flex-col gap-2 px-4 py-3 select-none [-webkit-touch-callout:none]"
        :class="[
          drag?.active && drag.target === cardKey(session) && drag.id !== cardKey(session) ? 'ring-2 ring-amber-400' : '',
          drag?.active && drag.id === cardKey(session) ? 'opacity-50' : '',
        ]"
        @pointerdown="reorder.onPointerDown($event, cardKey(session))"
        @pointermove="reorder.onPointerMove"
        @pointerup="reorder.onPointerUp"
        @pointercancel="reorder.cancel"
        @touchmove="reorder.onTouchMove"
        @contextmenu="drag?.active && $event.preventDefault()"
      >
        <div class="flex items-center gap-3">
          <div class="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-3">
            <h2 class="font-semibold">{{ sessionName(session) }}</h2>
            <span class="min-w-0 truncate text-xs text-slate-500">{{ session.path }}</span>
            <span class="text-sm text-slate-400">
              {{ labels.get(session.profile) ?? session.profile }}
              <span v-if="session.model" class="text-slate-500"> · {{ session.model }}</span>
            </span>
          </div>
          <!-- Status and the mode the next start uses, on the right: the action row below stays
               one line also on phones. -->
          <div class="flex shrink-0 flex-col items-end gap-1">
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
            <label v-if="workspaces" class="flex items-center gap-1 text-xs text-slate-400" :title="$t('sessions.workspace')">
              <select
                class="h-7 rounded-lg border border-slate-600 bg-slate-800 pr-1 pl-1.5 text-xs text-slate-200"
                :aria-label="$t('sessions.workspace')"
                :value="workspaceOf(session.id)"
                @change="moveToWorkspace(session, ($event.target as HTMLSelectElement).value)"
              >
                <option value="">{{ $t('workspace.unnamed') }}</option>
                <option v-for="name in workspaceNames" :key="name" :value="name">{{ name }}</option>
              </select>
            </label>
            <label
              v-if="permissionModes.get(session.profile)?.length"
              class="flex items-center gap-1 text-xs text-slate-400"
              :title="$t('permission.title')"
            >
              <select
                class="h-7 rounded-lg border border-slate-600 bg-slate-800 pr-1 pl-1.5 text-xs text-slate-200"
                :aria-label="$t('permission.label')"
                :value="session.permission_mode"
                @change="changePermissionMode(session, ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="mode in permissionModes.get(session.profile)" :key="mode" :value="mode">
                  {{ permissionLabel(mode) }}
                </option>
              </select>
            </label>
          </div>
        </div>
        <!-- Context left, effort right; where both do not fit in one row, the effort wraps. -->
        <div class="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
          <ContextMeter
            v-if="session.context_tokens != null && session.context_window != null"
            :tokens="session.context_tokens"
            :window="session.context_window"
          />
          <ReasoningControl
            v-if="session.running && session.effort_levels.length"
            compact
            :levels="session.effort_levels"
            :ultracode-offered="ultracodeOffered.get(session.profile) ?? false"
            :model-value="shownReasoning(session)"
            :disabled="session.effort_pending"
            @update:model-value="(reasoning) => (effortChange = { session, reasoning })"
          />
        </div>
        <ScheduledList :prompts="session.scheduled" />
        <!-- The context is large: a handover to a fresh session saves tokens (more so once cold). -->
        <div
          v-if="session.handover.recommended && !session.busy"
          class="flex flex-wrap items-center gap-2 rounded-lg border border-amber-700 bg-amber-950/40 px-3 py-2 text-sm text-amber-200"
        >
          <span class="flex-1">
            {{ $t('handover.advice', { percent: contextPercent(session) }) }}
            <span v-if="session.handover.cache_cold" class="text-amber-300/80"> · {{ $t('handover.cold') }}</span>
          </span>
          <button class="btn-secondary btn-small" :title="$t('handover.requestHint')" @click="requestHandover(session)">
            {{ $t('handover.request') }}
          </button>
        </div>
        <ApprovalRequests :session="session" />
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
            v-if="!effortLive.get(session.profile)"
            class="btn-secondary min-h-9"
            @click="applyPendingNow(session)"
          >
            {{ $t('sessions.applyNow') }}
          </button>
          <button class="btn min-h-9" @click="discardPending(session)">
            {{ $t('sessions.discard') }}
          </button>
        </div>
        <div
          v-if="session.pending_model"
          class="flex flex-wrap items-center gap-2 rounded-lg border border-amber-700 bg-amber-950/40 px-3 py-2 text-sm text-amber-200"
        >
          <span class="flex-1">{{ $t('sessions.modelPending', { model: session.pending_model }) }}</span>
          <button class="btn min-h-9" @click="discardPendingModel(session)">
            {{ $t('sessions.discard') }}
          </button>
        </div>
        <div class="flex flex-wrap gap-1.5">
          <RouterLink
            v-if="session.running"
            :to="terminalRoute(session.id)"
            class="btn-primary btn-small"
            :title="$t('sessions.terminal')"
            :aria-label="$t('sessions.terminal')"
          >
            <!-- On phones the icon only, so the action row stays one line. -->
            <AppIcon name="agents" /><span class="max-sm:hidden">{{ $t('sessions.terminal') }}</span>
          </RouterLink>
          <button
            v-if="!session.running && session.worktree"
            class="btn-secondary btn-small"
            :title="$t('worktree.remove')"
            @click="removingWorktree = session"
          >
            <AppIcon name="trash" />{{ $t('worktree.remove') }}
          </button>
          <button v-if="!session.running" class="btn-primary btn-small" @click="resume(session)">
            <AppIcon name="resume" />{{ $t('sessions.resume') }}
          </button>
          <RouterLink
            :to="`/changes/${encodeURIComponent(session.id)}`"
            class="btn-secondary btn-small-icon"
            :title="$t('changes.open')"
            :aria-label="$t('changes.button')"
          >
            <!-- The icon only (its name in the tooltip), so the row stays one line. -->
            <AppIcon name="diff" />
          </RouterLink>
          <TerminalButton v-if="!session.terminal" :path="session.path" :agent-id="session.id" button-class="btn-secondary btn-small-icon" />
          <DropdownMenu v-if="session.running" class="ml-auto" right panel-class="flex w-64 flex-col p-1">
            <template #trigger="{ toggle }">
              <button
                class="btn-secondary btn-small-icon"
                :title="$t('terminal.actions')"
                :aria-label="$t('terminal.actions')"
                @click="toggle"
              >
                <AppIcon name="more" />
              </button>
            </template>
            <AgentActions :session="session" @stop="stopping = session" />
          </DropdownMenu>
          <button
            v-else
            class="btn-secondary btn-small-icon"
            :title="$t('sessions.stop')"
            :aria-label="$t('sessions.stop')"
            @click="stopping = session"
          >
            <AppIcon name="stop" />
          </button>
        </div>
      </li>
    </ul>

    <BaseDialog v-if="effortChange" :title="$t('agent.effort')" @close="cancelEffort">
      <p class="mb-5 text-slate-300">
        {{
          $t(effortMessage(effortChange.session), {
            name: sessionName(effortChange.session),
            effort: reasoningLabel(effortChange.reasoning),
          })
        }}
      </p>
      <div class="flex flex-col gap-2">
        <template v-if="effortChange.session.busy">
          <button class="btn-primary" @click="applyEffort(false)">{{ $t('sessions.changeAfterAnswer') }}</button>
          <!-- A restart would end the answer; an agent that switches in place simply waits. -->
          <button v-if="!effortLive.get(effortChange.session.profile)" class="btn-danger" @click="applyEffort(true)">
            {{ $t('sessions.changeNow') }}
          </button>
        </template>
        <button v-else class="btn-primary" @click="applyEffort(false)">
          {{ $t(effortLive.get(effortChange.session.profile) ? 'sessions.changeEffortLive' : 'sessions.changeEffort') }}
        </button>
        <button class="btn" @click="cancelEffort">{{ $t('common.cancel') }}</button>
      </div>
    </BaseDialog>
    <ModelDialog
      v-if="resumingWithoutModel"
      :title="$t('sessions.resume')"
      :message="$t('restart.chooseModel', { name: sessionName(resumingWithoutModel) })"
      :confirm-label="$t('sessions.resume')"
      :profile="resumingWithoutModel.profile"
      :current-effort="resumingWithoutModel.effort"
      @choose="(choice) => resumingWithoutModel && resumeWith(resumingWithoutModel, choice.model, choice.effort)"
      @close="resumingWithoutModel = null"
    />
    <ConfirmDialog
      v-if="stopping"
      :title="$t('sessions.stop')"
      :message="$t('sessions.confirmStop', { name: sessionName(stopping) })"
      :confirm-label="$t('sessions.stop')"
      danger
      @confirm="confirmStop"
      @close="stopping = null"
    />
    <ConfirmDialog
      v-if="removingWorktree"
      :title="$t('worktree.remove')"
      :message="$t('worktree.confirm', { name: sessionName(removingWorktree) })"
      :confirm-label="$t('worktree.remove')"
      danger
      @confirm="confirmRemoveWorktree"
      @close="removingWorktree = null"
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
