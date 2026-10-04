<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { useToast } from '../composables/useToast'
import ToggleSwitch from './ToggleSwitch.vue'

// Whether the server asks idle agents with a large context for their handover by itself; kept
// on the server, which does it also when no device is open.
const toast = useToast()
const auto = ref(false)

onMounted(async () => {
  try {
    auto.value = (await api.handoverAuto()).auto
  } catch (error) {
    toast.error(error)
  }
})

async function toggle(): Promise<void> {
  try {
    await api.setHandoverAuto(!auto.value)
    auto.value = !auto.value
  } catch (error) {
    toast.error(error)
  }
}
</script>

<template>
  <div class="mt-3 border-t border-slate-700 pt-3 text-sm text-slate-300">
    <div class="flex items-center justify-between gap-2">
      <span>{{ $t('handover.auto') }}</span>
      <ToggleSwitch class="h-7" :checked="auto" :aria-label="$t('handover.auto')" @click="toggle" />
    </div>
    <p class="mt-1 text-xs text-slate-500">{{ $t('handover.autoHint') }}</p>
  </div>
</template>
