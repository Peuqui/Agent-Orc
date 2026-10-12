<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, type DictationService } from '../../api'
import { useSettings } from '../../composables/useSettings'
import { useToast } from '../../composables/useToast'
import ToggleSwitch from '../ToggleSwitch.vue'

// The dictation. What the Whisper service uses is the service's own business and only shown; where it
// transcribes (CPU or GPU) and whether a dictation goes to the agent at once are the same on every device.
const { dictationDevice, dictationSendsAtOnce } = useSettings()
const toast = useToast()
// What the Whisper service transcribes with; asked when the window opens.
const service = ref<DictationService | null>(null)
onMounted(async () => {
  try {
    service.value = (await api.dictationSettings()).service
  } catch (error) {
    toast.error(error)
  }
})
</script>

<template>
  <div>
    <div v-if="service" class="text-sm text-slate-300">
      <span>{{ $t('settings.dictationService') }}</span>
      <p class="mt-1 text-xs text-slate-400 capitalize">
        {{ $t('settings.dictationServiceLine', service) }}
      </p>
      <p class="mt-1 text-xs text-slate-500">{{ $t('settings.dictationServiceHint') }}</p>
    </div>
    <!-- The dictation: where Whisper transcribes (CPU or GPU) and whether it goes to the agent at once; for this device. -->
    <div class="mt-4 border-t border-slate-700 pt-3 text-sm text-slate-300">
      <div v-if="service" class="flex items-center justify-between gap-2">
        <span>{{ $t('settings.dictationDevice') }}</span>
        <div class="flex overflow-hidden rounded-md border border-slate-600 text-xs">
          <button
            v-for="choice in (['cpu', 'cuda'] as const)"
            :key="choice"
            class="px-2 py-1"
            :class="dictationDevice === choice ? 'bg-slate-600 text-slate-100' : 'text-slate-400'"
            @click="dictationDevice = choice"
          >
            {{ choice === 'cuda' ? 'GPU' : 'CPU' }}
          </button>
        </div>
      </div>
      <p v-if="service" class="mt-1 text-xs text-slate-500">{{ $t('settings.dictationDeviceHint') }}</p>
      <ToggleSwitch class="mt-2 h-7 text-slate-300" :checked="dictationSendsAtOnce" @click="dictationSendsAtOnce = !dictationSendsAtOnce">
        {{ $t('settings.dictationSendsAtOnce') }}
      </ToggleSwitch>
      <p class="mt-1 text-xs text-slate-500">{{ $t('settings.dictationSendsAtOnceHint') }}</p>
    </div>

  </div>
</template>
