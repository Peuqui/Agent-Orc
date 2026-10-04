<script setup lang="ts">
import { computed, ref } from 'vue'
import { api, type AgentSession } from '../api'
import AppIcon from '../components/AppIcon.vue'
import BaseDialog from '../components/BaseDialog.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import ContextMeter from '../components/ContextMeter.vue'
import QuotaPanel from '../components/QuotaPanel.vue'
import { useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import { baseName } from '../format'

const { sessions, profiles, refresh } = useSessions()
const toast = useToast()
const stopping = ref<AgentSession | null>(null)
const effortChange = ref<{
  session: AgentSession
  effort: string | null
  select: HTMLSelectElement
} | null>(null)

const levels = computed(() => new Map(profiles.value.map((p) => [p.name, p.effort_levels])))

// Cancelled: show the effort that is actually in effect again.
function cancelEffort(): void {
  const change = effortChange.value
  effortChange.value = null
  if (change) change.select.value = change.session.effort ?? ''
}

function applyPendingNow(session: AgentSession): void {
  void run(() => api.changeEffort(session.id, session.pending_effort, true))
}

function discardPending(session: AgentSession): void {
  void run(() => api.cancelEffortChange(session.id))
}

function applyEffort(immediately: boolean): void {
  const change = effortChange.value
  effortChange.value = null
  if (change) void run(() => api.changeEffort(change.session.id, change.effort, immediately))
}

const labels = computed(() => new Map(profiles.value.map((p) => [p.name, p.label])))
const sorted = computed(() =>
  [...sessions.value].sort((a, b) => baseName(a.path).localeCompare(baseName(b.path))),
)

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
  void run(() => api.startSession(session.profile, session.path, true, session.effort))
}
</script>

<template>
  <section>
    <!-- Always reachable: a new agent starts in a folder chosen in the file view. -->
    <QuotaPanel />
    <RouterLink to="/files" class="btn-primary mb-4 w-full sm:w-auto">
      <AppIcon name="plus" />{{ $t('sessions.startNew') }}
    </RouterLink>
    <p v-if="sorted.length === 0" class="card p-6 text-center text-slate-400">{{ $t('sessions.empty') }}</p>

    <ul class="flex flex-col gap-3">
      <li v-for="session in sorted" :key="session.id" class="card p-4">
        <div class="mb-3 flex items-start justify-between gap-3">
          <div class="min-w-0">
            <h2 class="truncate font-semibold">{{ baseName(session.path) }}</h2>
            <p class="truncate text-xs text-slate-500">{{ session.path }}</p>
            <p class="mt-1 text-sm text-slate-400">
              {{ labels.get(session.profile) ?? session.profile }}
              <span v-if="session.model" class="text-slate-500"> · {{ session.model }}</span>
              <span v-if="session.effort" class="text-slate-500"> · {{ session.effort }}</span>
            </p>
          </div>
          <span
            v-if="session.running && session.busy"
            class="shrink-0 animate-pulse rounded-full bg-amber-900/40 px-2.5 py-1 text-xs font-medium text-amber-300"
          >
            {{ $t('sessions.working') }}
          </span>
          <span
            v-else
            class="shrink-0 rounded-full px-2.5 py-1 text-xs font-medium"
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
        <ContextMeter
          v-if="session.context_tokens != null && session.context_window != null"
          class="mb-3"
          :tokens="session.context_tokens"
          :window="session.context_window"
        />
        <label
          v-if="session.running && levels.get(session.profile)?.length"
          class="mb-3 flex items-center gap-2 text-sm text-slate-400"
        >
          {{ $t('agent.effort') }}
          <select
            class="h-9 rounded-md border border-slate-600 bg-slate-900 px-2 text-slate-200"
            :disabled="session.effort_pending"
            :value="session.effort ?? ''"
            @change="
              effortChange = {
                session,
                effort: ($event.target as HTMLSelectElement).value || null,
                select: $event.target as HTMLSelectElement,
              }
            "
          >
            <option value="">{{ $t('agent.effortDefault') }}</option>
            <option v-for="level in levels.get(session.profile)" :key="level" :value="level">
              {{ level }}
            </option>
          </select>
        </label>
        <div
          v-if="session.effort_pending"
          class="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-amber-700 bg-amber-950/40 px-3 py-2 text-sm text-amber-200"
        >
          <span class="flex-1">
            {{ $t('sessions.effortPending', { effort: session.pending_effort ?? $t('agent.effortDefault') }) }}
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
            class="btn-primary"
          >
            <AppIcon name="agents" />{{ $t('sessions.terminal') }}
          </RouterLink>
          <button v-if="!session.running" class="btn-primary" @click="resume(session)">
            <AppIcon name="resume" />{{ $t('sessions.resume') }}
          </button>
          <button class="btn-secondary" @click="stopping = session">
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
            effort: effortChange.effort ?? $t('agent.effortDefault'),
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
  </section>
</template>
