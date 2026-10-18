<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { useToast } from '../composables/useToast'
import ToggleSwitch from './ToggleSwitch.vue'

// Whether the server keeps the prompt cache of resting agents warm by itself; the default for all agents,
// each can deviate on its card. Kept on the server, which does it also when no device is open.
const toast = useToast()
const keepWarm = ref(false)

onMounted(async () => {
  try {
    keepWarm.value = (await api.keepWarmDefault()).default
  } catch (error) {
    toast.error(error)
  }
})

async function toggle(): Promise<void> {
  try {
    await api.setKeepWarmDefault(!keepWarm.value)
    keepWarm.value = !keepWarm.value
  } catch (error) {
    toast.error(error)
  }
}
</script>

<template>
  <div class="text-sm text-slate-300">
    <div class="flex items-center justify-between gap-2">
      <span>{{ $t('keepWarm.default') }}</span>
      <ToggleSwitch class="h-7" :checked="keepWarm" :aria-label="$t('keepWarm.default')" @click="toggle" />
    </div>
    <p class="mt-1 text-xs text-slate-500">{{ $t('keepWarm.defaultHint') }}</p>
  </div>
</template>
