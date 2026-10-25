<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, type HandoverSettings } from '../api'
import { useToast } from '../composables/useToast'
import ToggleSwitch from './ToggleSwitch.vue'

// Whether the server asks agents with a nearly full context for their handover itself; kept on
// the server, which does it also when no device is open. The shares come from its config.
const toast = useToast()
const settings = ref<HandoverSettings | null>(null)

onMounted(async () => {
  try {
    settings.value = await api.handover()
  } catch (error) {
    toast.error(error)
  }
})

async function change(current: HandoverSettings, wanted: { auto?: boolean; fresh?: boolean }): Promise<void> {
  const auto = wanted.auto ?? current.auto
  const fresh = wanted.fresh ?? current.fresh
  try {
    await api.setHandover(auto, fresh)
    current.auto = auto
    current.fresh = fresh
  } catch (error) {
    toast.error(error)
  }
}
</script>

<template>
  <div v-if="settings" class="text-sm text-slate-300">
    <div class="flex items-center justify-between gap-2">
      <span>{{ $t('handover.auto') }}</span>
      <ToggleSwitch class="h-7" :checked="settings.auto" :aria-label="$t('handover.auto')" @click="change(settings, { auto: !settings.auto })" />
    </div>
    <p class="mt-1 text-xs text-slate-500">
      {{ $t('handover.autoHint', { advice: settings.advice_percent, threshold: settings.threshold_percent }) }}
    </p>
    <div class="mt-3 flex items-center justify-between gap-2" :class="{ 'opacity-50': !settings.auto }">
      <span>{{ $t('handover.fresh') }}</span>
      <ToggleSwitch class="h-7" :checked="settings.fresh" :aria-label="$t('handover.fresh')" @click="change(settings, { fresh: !settings.fresh })" />
    </div>
    <p class="mt-1 text-xs text-slate-500">{{ $t('handover.freshHint') }}</p>
  </div>
</template>
