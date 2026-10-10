<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type ConsumptionRow } from '../api'
import { useHosts } from '../composables/useHosts'
import { useToast } from '../composables/useToast'
import { useTokenFormat } from '../composables/useTokenFormat'
import { baseName } from '../format'

// Claude's token consumption from all its conversations (Agent-Orc, terminal, VS Code, subagents),
// of all machines added up or of one: per day as bars, per project, model and machine as tables.
// Tokens, no prices: those change, and a subscription does not bill them.
const PERIODS = [7, 14, 30]
const MILLISECONDS_PER_DAY = 24 * 60 * 60 * 1000
const KINDS = ['input', 'cache_write', 'cache_read', 'output'] as const

type MachineRow = ConsumptionRow & { machine: string }
const ALL = ''

const toast = useToast()
const { locale } = useI18n()
const formatTokens = useTokenFormat()
const { state: hosts, loadHosts } = useHosts()
const loaded = ref<MachineRow[] | null>(null)
const period = ref(14)
// One machine's name, or ALL for every machine added up.
const shown = ref(ALL)

// This machine's consumption and that of each machine that answers.
async function load(): Promise<void> {
  await loadHosts()
  const state = hosts.value!
  const machines = [{ name: state.self, host: undefined }, ...state.hosts.filter((host) => host.online).map((host) => ({ name: host.name, host: host.name }))]
  const perMachine = await Promise.all(
    machines.map(async ({ name, host }) => (await api.consumption(host)).map((row) => ({ ...row, machine: name }))),
  )
  loaded.value = perMachine.flat()
}

load().catch(toast.error)

const machines = computed(() => [...new Set((loaded.value ?? []).map((row) => row.machine))])
const unreachable = computed(() => (hosts.value?.hosts ?? []).filter((host) => !host.online).map((host) => host.name))
const rows = computed(() => (loaded.value ?? []).filter((row) => shown.value === ALL || row.machine === shown.value))
// Several machines in the sums: the project and machine tables tell them apart.
const several = computed(() => shown.value === ALL && machines.value.length > 1)

function localDay(date: Date): string {
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return shifted.toISOString().slice(0, 10)
}

const days = computed(() =>
  Array.from({ length: period.value }, (_unused, index) =>
    localDay(new Date(Date.now() - (period.value - 1 - index) * MILLISECONDS_PER_DAY)),
  ),
)
const inPeriod = computed(() => rows.value.filter((row) => row.day >= days.value[0]!))

function total(row: Pick<ConsumptionRow, (typeof KINDS)[number]>): number {
  return KINDS.reduce((sum, kind) => sum + row[kind], 0)
}

type Sums = Record<(typeof KINDS)[number] | 'messages', number>

function sumBy(key: (row: MachineRow) => string): [string, Sums][] {
  const sums = new Map<string, Sums>()
  for (const row of inPeriod.value) {
    const name = key(row)
    const entry = sums.get(name) ?? { input: 0, cache_write: 0, cache_read: 0, output: 0, messages: 0 }
    for (const kind of [...KINDS, 'messages'] as const) entry[kind] += row[kind]
    sums.set(name, entry)
  }
  return [...sums.entries()].sort((a, b) => total(b[1]) - total(a[1]))
}

const perDay = computed(() => new Map(sumBy((row) => row.day)))
const perProject = computed(() =>
  sumBy((row) => {
    const name = baseName(row.project) || row.project
    return several.value ? `${name} · ${row.machine}` : name
  }),
)
const perMachine = computed(() => sumBy((row) => row.machine))
const perModel = computed(() => sumBy((row) => row.model))
const highest = computed(() => Math.max(1, ...[...perDay.value.values()].map(total)))
const overall = computed(() => sumBy(() => 'all')[0]?.[1])

function dayLabel(day: string): string {
  return new Date(`${day}T12:00:00`).toLocaleDateString(locale.value, { weekday: 'short', day: 'numeric' })
}
</script>

<template>
  <section class="flex flex-col gap-4">
    <div class="flex flex-wrap items-center gap-2">
      <h1 class="flex-1 text-lg font-semibold">{{ $t('consumption.title') }}</h1>
      <div class="flex overflow-hidden rounded-md border border-slate-600 text-sm">
        <button
          v-for="days_ in PERIODS"
          :key="days_"
          class="px-3 py-1"
          :class="period === days_ ? 'bg-slate-600 text-slate-100' : 'text-slate-400 hover:bg-slate-700'"
          @click="period = days_"
        >
          {{ $t('consumption.days', { count: days_ }) }}
        </button>
      </div>
    </div>
    <p class="text-xs text-slate-500">{{ $t('consumption.hint') }}</p>
    <div v-if="machines.length > 1 || unreachable.length" class="flex flex-wrap items-center gap-2 text-sm">
      <button
        v-for="choice in [ALL, ...machines]"
        :key="choice"
        class="rounded-full border px-3 py-0.5"
        :class="shown === choice ? 'border-amber-500 bg-amber-900/30 text-amber-300' : 'border-slate-600 text-slate-400 hover:bg-slate-800'"
        @click="shown = choice"
      >
        {{ choice === ALL ? $t('consumption.allMachines') : choice }}
      </button>
      <span v-for="name in unreachable" :key="name" class="text-xs text-slate-500">{{ $t('consumption.unreachable', { name }) }}</span>
    </div>
    <p v-if="!loaded" class="card p-6 text-center text-slate-400">{{ $t('consumption.loading') }}</p>
    <template v-else>
      <div v-if="overall" class="card grid grid-cols-2 gap-3 p-4 text-sm sm:grid-cols-5">
        <div v-for="kind in [...KINDS, 'messages'] as const" :key="kind">
          <div class="text-xs text-slate-500">{{ $t(`consumption.kind.${kind}`) }}</div>
          <div class="text-lg font-semibold text-slate-100">{{ formatTokens(overall[kind]) }}</div>
        </div>
      </div>

      <div class="card p-4">
        <h2 class="mb-3 text-sm font-semibold text-slate-300">{{ $t('consumption.perDay') }}</h2>
        <div class="flex h-40 items-end gap-1">
          <div v-for="day in days" :key="day" class="flex h-full min-w-0 flex-1 flex-col justify-end" :title="`${day}: ${formatTokens(perDay.get(day) ? total(perDay.get(day)!) : 0)}`">
            <div
              class="rounded-t bg-red-500/70"
              :style="{ height: `${((perDay.get(day) ? total(perDay.get(day)!) : 0) / highest) * 100}%` }"
            />
          </div>
        </div>
        <div class="mt-1 flex gap-1 text-[10px] text-slate-500">
          <span v-for="day in days" :key="day" class="min-w-0 flex-1 truncate text-center">{{ dayLabel(day) }}</span>
        </div>
      </div>

      <div
        v-for="table in [{ key: 'perProject', rows: perProject }, { key: 'perModel', rows: perModel }, ...(several ? [{ key: 'perMachine', rows: perMachine }] : [])]"
        :key="table.key"
        class="card overflow-x-auto p-4"
      >
        <h2 class="mb-2 text-sm font-semibold text-slate-300">{{ $t(`consumption.${table.key}`) }}</h2>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-xs text-slate-500">
              <th class="py-1 pr-3 font-normal">{{ $t(`consumption.${table.key}Column`) }}</th>
              <th v-for="kind in [...KINDS, 'messages'] as const" :key="kind" class="py-1 pl-3 text-right font-normal">
                {{ $t(`consumption.kind.${kind}`) }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="[name, sums] in table.rows" :key="name" class="border-t border-slate-700">
              <td class="max-w-48 truncate py-1 pr-3 text-slate-200">{{ name }}</td>
              <td v-for="kind in [...KINDS, 'messages'] as const" :key="kind" class="py-1 pl-3 text-right text-slate-300 tabular-nums">
                {{ formatTokens(sums[kind]) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>
