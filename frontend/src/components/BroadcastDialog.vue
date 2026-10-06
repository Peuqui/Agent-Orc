<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { sessionName, useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import AppIcon from './AppIcon.vue'
import BaseDialog from './BaseDialog.vue'
import ToggleSwitch from './ToggleSwitch.vue'

// One prompt for the chosen agents, e.g. "commit and push", "read the new CLAUDE.md" or a note;
// typed into each as if the user did it there.
const props = withDefaults(defineProps<{ initialText?: string; submit?: boolean }>(), { initialText: '', submit: true })
const emit = defineEmits<{ close: [] }>()
const { t } = useI18n()
const toast = useToast()
const { sessions, refresh } = useSessions()

const chosen = ref<string[]>([])
const text = ref(props.initialText)
// Whether the text is also submitted, or only put into each agent's input to be sent there.
const submit = ref(props.submit)
const running = computed(() => sessions.value.filter((session) => session.running))

async function send(): Promise<void> {
  try {
    await api.broadcast(chosen.value, text.value.trim(), submit.value)
    emit('close')
    toast.info(t('broadcast.sent', { count: chosen.value.length }))
  } catch (error) {
    toast.error(error)
  }
  await refresh()
}
</script>

<template>
  <BaseDialog :title="$t('broadcast.title')" @close="emit('close')">
    <form class="flex flex-col gap-3" @submit.prevent="send">
      <div class="flex max-h-[40dvh] flex-col gap-1 overflow-y-auto">
        <label
          v-for="session in running"
          :key="session.id"
          class="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-slate-700"
        >
          <input v-model="chosen" type="checkbox" :value="session.id" class="size-4" />
          <span class="font-medium">{{ sessionName(session) }}</span>
          <span v-if="session.busy" class="text-xs text-amber-300">{{ $t('sessions.working') }}</span>
        </label>
      </div>
      <textarea v-model="text" rows="4" class="input text-sm" :placeholder="$t('broadcast.text')" required />
      <ToggleSwitch class="h-7 self-start text-sm text-slate-300" :checked="submit" @click="submit = !submit">
        {{ $t('broadcast.submit') }}
      </ToggleSwitch>
      <div class="flex gap-2">
        <button type="submit" class="btn-primary flex-1" :disabled="!chosen.length || !text.trim()">
          <AppIcon name="send" />{{ $t(submit ? 'broadcast.send' : 'broadcast.insert', { count: chosen.length }) }}
        </button>
        <button type="button" class="btn" @click="emit('close')">{{ $t('common.cancel') }}</button>
      </div>
    </form>
  </BaseDialog>
</template>
