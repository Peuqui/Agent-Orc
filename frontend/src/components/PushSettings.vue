<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { pushSupported, usePush } from '../composables/usePush'
import { useToast } from '../composables/useToast'
import ToggleSwitch from './ToggleSwitch.vue'

// Notifications on this device when an agent finished or waits for a permission or an answer.
const { subscribed, refresh, enable, disable } = usePush()
const toast = useToast()
const { t } = useI18n()
const working = ref(false)

onMounted(() => refresh().catch(toast.error))

async function toggle(): Promise<void> {
  working.value = true
  try {
    if (subscribed.value) await disable()
    else if (!(await enable())) toast.info(t('push.denied'))
  } catch (error) {
    toast.error(error)
  } finally {
    working.value = false
  }
}

async function sendTest(): Promise<void> {
  try {
    const { delivered } = await api.testPush()
    toast.info(t('push.testSent', { count: delivered }))
  } catch (error) {
    toast.error(error)
  }
}
</script>

<template>
  <div class="mt-3 border-t border-slate-700 pt-3 text-sm text-slate-300">
    <div class="flex items-center justify-between gap-2">
      <span>{{ $t('push.title') }}</span>
      <ToggleSwitch
        v-if="pushSupported"
        class="h-7"
        :checked="subscribed"
        :disabled="working"
        :aria-label="$t('push.title')"
        @click="toggle"
      />
    </div>
    <p class="mt-1 text-xs text-slate-500">
      {{ pushSupported ? $t('push.hint') : $t('push.unsupported') }}
    </p>
    <button v-if="subscribed" class="btn-secondary btn-small mt-2" @click="sendTest">
      {{ $t('push.test') }}
    </button>
  </div>
</template>
