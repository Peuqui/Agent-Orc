<script setup lang="ts">
import { FitAddon } from '@xterm/addon-fit'
import { Terminal } from '@xterm/xterm'
import '@xterm/xterm/css/xterm.css'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, terminalUrl, type Modifier, type TerminalSettings } from '../api'
import AppIcon from '../components/AppIcon.vue'
import ContextMeter from '../components/ContextMeter.vue'
import KeyBar from '../components/KeyBar.vue'
import { useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import { baseName } from '../format'

const props = defineProps<{ id: string }>()

const FONT_SIZE_KEY = 'ai-orc-terminal-font-size'
const DEFAULT_FONT_SIZE = 14
const MIN_FONT_SIZE = 8
const MAX_FONT_SIZE = 28
const SCROLLBACK_LINES = 5000
const ESC = '\x1b'
// Ctrl+letter is the letter's code minus 64 ('@'): Ctrl+C = 0x03.
const CTRL_OFFSET = 64
const CTRL_RANGE_END = 95

const router = useRouter()
const toast = useToast()
const { sessions } = useSessions()

const container = ref<HTMLElement>()
const settings = ref<TerminalSettings | null>(null)
const modifiers = ref(new Set<Modifier>())
const text = ref('')
const connected = ref(false)
const fontSize = ref(Number(localStorage.getItem(FONT_SIZE_KEY)) || DEFAULT_FONT_SIZE)

const session = computed(() => sessions.value.find((candidate) => candidate.id === props.id))
const name = computed(() => (session.value ? baseName(session.value.path) : props.id))

const terminal = new Terminal({
  fontSize: fontSize.value,
  fontFamily: 'ui-monospace, "Cascadia Mono", "DejaVu Sans Mono", monospace',
  cursorBlink: true,
  scrollback: SCROLLBACK_LINES,
  theme: {
    background: '#0f172a',
    foreground: '#f1f5f9',
    cursor: '#ef4444',
    selectionBackground: '#7f1d1d',
  },
})
const fit = new FitAddon()
terminal.loadAddon(fit)
let socket: WebSocket | null = null
const resizeObserver = new ResizeObserver(() => fit.fit())

function send(message: object): void {
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message))
}

function sendInput(data: string): void {
  send({ type: 'input', data })
}

/** Apply latched Ctrl/Alt to the next input, then release them (Termux-style). */
function withModifiers(data: string): string {
  let result = data
  if (modifiers.value.has('ctrl') && data.length === 1) {
    const code = data.toUpperCase().charCodeAt(0)
    if (code >= CTRL_OFFSET && code <= CTRL_RANGE_END) result = String.fromCharCode(code - CTRL_OFFSET)
  }
  if (modifiers.value.has('alt')) result = ESC + result
  modifiers.value = new Set()
  return result
}

function toggleModifier(modifier: Modifier): void {
  const next = new Set(modifiers.value)
  if (next.has(modifier)) next.delete(modifier)
  else next.add(modifier)
  modifiers.value = next
}

function submitText(): void {
  if (!settings.value || !text.value) return
  sendInput(text.value)
  // Enter separately, so the agent sees typed text plus submit, not one pasted block.
  window.setTimeout(() => sendInput('\r'), settings.value.submit_delay_ms)
  text.value = ''
}

function changeFontSize(delta: number): void {
  fontSize.value = Math.min(MAX_FONT_SIZE, Math.max(MIN_FONT_SIZE, fontSize.value + delta))
  localStorage.setItem(FONT_SIZE_KEY, String(fontSize.value))
  terminal.options.fontSize = fontSize.value
  fit.fit()
}

function connect(): void {
  socket = new WebSocket(terminalUrl(props.id))
  socket.binaryType = 'arraybuffer'
  socket.onopen = () => {
    connected.value = true
    send({ type: 'resize', cols: terminal.cols, rows: terminal.rows })
    terminal.focus()
  }
  socket.onmessage = (event: MessageEvent<ArrayBuffer>) => terminal.write(new Uint8Array(event.data))
  socket.onclose = () => {
    connected.value = false
  }
}

terminal.onData((data) => sendInput(withModifiers(data)))
terminal.onResize(({ cols, rows }) => send({ type: 'resize', cols, rows }))

onMounted(async () => {
  try {
    settings.value = await api.terminalSettings()
  } catch (error) {
    toast.error(error)
  }
  if (!container.value) return
  terminal.open(container.value)
  fit.fit()
  resizeObserver.observe(container.value)
  connect()
})

onBeforeUnmount(() => {
  resizeObserver.disconnect()
  socket?.close()
  terminal.dispose()
})
</script>

<template>
  <div class="flex h-dvh flex-col bg-slate-900">
    <header class="flex items-center gap-1 border-b border-slate-800 px-1 py-1">
      <button class="btn-icon" :aria-label="$t('terminal.back')" @click="router.push('/sessions')">
        <AppIcon name="up" class="-rotate-90" />
      </button>
      <h1 class="min-w-0 flex-1 truncate font-semibold">{{ name }}</h1>
      <ContextMeter
        v-if="session && session.context_tokens != null && session.context_window != null"
        compact
        :tokens="session.context_tokens"
        :window="session.context_window"
      />
      <span class="size-2.5 rounded-full" :class="connected ? 'bg-red-500' : 'bg-slate-600'" />
      <button class="btn-icon text-sm" :aria-label="$t('terminal.smaller')" @click="changeFontSize(-1)">A−</button>
      <button class="btn-icon text-base" :aria-label="$t('terminal.larger')" @click="changeFontSize(1)">A+</button>
    </header>

    <div class="relative min-h-0 flex-1 px-1 pt-1">
      <div ref="container" class="h-full w-full" />
      <div
        v-if="!connected"
        class="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-slate-900/85"
      >
        <p class="text-slate-300">{{ $t('terminal.disconnected') }}</p>
        <button class="btn-primary" @click="connect">{{ $t('terminal.reconnect') }}</button>
      </div>
    </div>

    <form class="flex gap-1 border-t border-slate-800 p-1" @submit.prevent="submitText">
      <input
        v-model="text"
        class="input min-h-10 flex-1"
        :placeholder="$t('terminal.placeholder')"
        enterkeyhint="send"
      />
      <button type="submit" class="btn-primary min-h-10 px-3" :disabled="!text">{{ $t('terminal.send') }}</button>
    </form>

    <KeyBar
      v-if="settings"
      :rows="settings.keys"
      :active="modifiers"
      @send="(sequence) => sendInput(withModifiers(sequence))"
      @toggle="toggleModifier"
    />
  </div>
</template>
