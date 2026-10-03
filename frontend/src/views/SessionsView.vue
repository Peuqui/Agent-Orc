<script setup lang="ts">
import { computed, ref } from 'vue'
import { api, type AgentSession } from '../api'
import AppIcon from '../components/AppIcon.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import { baseName } from '../format'

const { sessions, profiles, refresh } = useSessions()
const toast = useToast()
const stopping = ref<AgentSession | null>(null)

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
  void run(() => api.startSession(session.profile, session.path, true))
}
</script>

<template>
  <section>
    <div v-if="sorted.length === 0" class="card p-6 text-center text-slate-400">
      <p class="mb-4">{{ $t('sessions.empty') }}</p>
      <RouterLink to="/files" class="btn-primary"><AppIcon name="play" />{{ $t('sessions.startNew') }}</RouterLink>
    </div>

    <ul class="flex flex-col gap-3">
      <li v-for="session in sorted" :key="session.id" class="card p-4">
        <div class="mb-3 flex items-start justify-between gap-3">
          <div class="min-w-0">
            <h2 class="truncate font-semibold">{{ baseName(session.path) }}</h2>
            <p class="truncate text-xs text-slate-500">{{ session.path }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ labels.get(session.profile) ?? session.profile }}</p>
          </div>
          <span
            class="shrink-0 rounded-full px-2.5 py-1 text-xs font-medium"
            :class="session.running ? 'bg-red-900/40 text-red-300' : 'bg-slate-700 text-slate-300'"
          >
            {{ session.running ? $t('sessions.running') : $t('sessions.exited', { code: session.exit_status }) }}
          </span>
        </div>
        <div class="flex flex-wrap gap-2">
          <RouterLink v-if="session.running" :to="`/terminal/${session.id}`" class="btn-primary">
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
