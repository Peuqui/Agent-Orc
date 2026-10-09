<script setup lang="ts">
import { computed, onMounted, ref, useTemplateRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { errorText, TOAST_MILLISECONDS } from '../composables/useToast'
import { isSendKey } from '../sendKey'

// A field to write to peers as the user: below an open conversation (to those in it) and at the
// page's foot (to whom the slot lets one choose). Enter sends, Shift+Enter breaks the line.
// `focused` puts the cursor in the field as it appears (asked for by "Answer").
const props = defineProps<{ recipients: string[]; placeholder: string; focused?: boolean }>()
const { t } = useI18n()

const text = ref('')
const sending = ref(false)
// What came of sending, shown just above the field where the eye is, instead of a toast far below.
const notice = ref<{ text: string; error: boolean } | null>(null)
let noticeTimer: ReturnType<typeof setTimeout> | undefined
const field = useTemplateRef<HTMLTextAreaElement>('field')

const canSend = computed(() => props.recipients.length > 0 && text.value.trim() !== '' && !sending.value)

function onKeydown(event: KeyboardEvent): void {
  if (!isSendKey(event)) return
  event.preventDefault()
  if (canSend.value) void send()
}

async function send(): Promise<void> {
  sending.value = true
  try {
    const result = await api.peerMessage(props.recipients, text.value.trim())
    const offline = result.sent.filter((sent) => !sent.online).map((sent) => sent.to)
    text.value = ''
    showNotice(offline.length ? t('peers.sentOffline', { names: offline.join(', ') }) : t('peers.sent'), false)
  } catch (error) {
    showNotice(errorText(error), true)
  } finally {
    sending.value = false
  }
}

function showNotice(text: string, error: boolean): void {
  clearTimeout(noticeTimer)
  notice.value = { text, error }
  noticeTimer = setTimeout(() => (notice.value = null), TOAST_MILLISECONDS)
}

onMounted(() => {
  if (!props.focused) return
  field.value?.focus()
  // Focus leaves a field alone that is in the window but under the page's foot; this honours its
  // scroll margin.
  field.value?.scrollIntoView({ block: 'nearest' })
})
</script>

<template>
  <form class="flex flex-col gap-2" @submit.prevent="send">
    <p v-if="notice" class="text-sm" :class="notice.error ? 'text-red-300' : 'text-emerald-300'" role="status">
      {{ notice.text }}
    </p>
    <slot />
    <div class="flex items-end gap-2">
      <textarea
        ref="field"
        v-model="text"
        rows="1"
        enterkeyhint="send"
        class="input max-h-40 min-w-0 flex-1 resize-none [field-sizing:content]"
        :placeholder="placeholder"
        @keydown="onKeydown"
      />
      <button type="submit" class="btn-primary btn-small" :disabled="!canSend">{{ $t('peers.send') }}</button>
    </div>
  </form>
</template>
