<script setup lang="ts">
import { ClipboardAddon } from '@xterm/addon-clipboard'
import { FitAddon } from '@xterm/addon-fit'
import { Unicode11Addon } from '@xterm/addon-unicode11'
import { WebglAddon } from '@xterm/addon-webgl'
import { WebLinksAddon } from '@xterm/addon-web-links'
import { Terminal } from '@xterm/xterm'
import '@xterm/xterm/css/xterm.css'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { api, terminalUrl, type Modifier, type TerminalSettings } from '../api'
import AppIcon from '../components/AppIcon.vue'
import ContextMeter from '../components/ContextMeter.vue'
import RestartButton from '../components/RestartButton.vue'
import TerminalButton from '../components/TerminalButton.vue'
import JogScroller from '../components/JogScroller.vue'
import KeyBar from '../components/KeyBar.vue'
import MessageInput from '../components/MessageInput.vue'
import { registerFileLinks } from '../composables/useFileLinks'
import { sessionName, useSessions } from '../composables/useSessions'
import { PHONE_WIDTH } from '../device'
import { useToast } from '../composables/useToast'
import {
  FONT_SAMPLE,
  TERMINAL_FONTS,
  type TerminalFont,
  useSettings,
} from '../composables/useSettings'
import { COLUMN_CLOSE_EVENT, COLUMN_FULLSCREEN_EVENT, COLUMN_SWIPE_EVENT } from '../columns'
import { useTouchScroll } from '../composables/useTouchScroll'

const props = defineProps<{ id: string; embedded: boolean }>()

const SCROLLBACK_LINES = 5000
const ESC = '\x1b'
// Ctrl+letter is the letter's code minus 64 ('@'): Ctrl+C = 0x03.
const CTRL_OFFSET = 64
const CTRL_RANGE_END = 95

const router = useRouter()
const { t } = useI18n()
const toast = useToast()
const { sessions } = useSessions()

const container = ref<HTMLElement>()
const messageInput = ref<InstanceType<typeof MessageInput>>()
const settings = ref<TerminalSettings | null>(null)
const modifiers = ref(new Set<Modifier>())
const connected = ref(false)
// A−/A+ give this terminal its own size; otherwise it follows the size set in the settings.
// One font size for every terminal of this device (settings menu, or ⋯ on phones).
const { lineHeight, fontSize, stepFontSize, terminalFont, extraKeysVersion } = useSettings()

// Arranged anew (on this or another column of the device): fetch the keys again.
watch(extraKeysVersion, async () => {
  try {
    settings.value = await api.terminalSettings()
  } catch (error) {
    toast.error(error)
  }
})

// Plain-text view: the canvas terminal cannot be selected on a phone, ordinary text can.
const plainText = ref<string | null>(null)
const plainTextBox = ref<HTMLElement>()

async function showPlainText(): Promise<void> {
  try {
    plainText.value = (await api.sessionText(props.id)).text
    await nextTick()
    // Newest output is at the end.
    plainTextBox.value?.scrollTo({ top: plainTextBox.value.scrollHeight })
  } catch (error) {
    toast.error(error)
  }
}

async function copyPlainText(): Promise<void> {
  if (plainText.value === null) return
  try {
    await navigator.clipboard.writeText(plainText.value)
    toast.info(t('terminal.copied'))
  } catch (error) {
    toast.error(error)
  }
}

const session = computed(() => sessions.value.find((candidate) => candidate.id === props.id))
const name = computed(() => (session.value ? sessionName(session.value) : props.id))

// A workspace column on a phone has no tab of its own: the bar names it and closes it.
const phone = ref(PHONE_WIDTH.matches)
const followPhoneWidth = (event: MediaQueryListEvent): void => {
  phone.value = event.matches
}
PHONE_WIDTH.addEventListener('change', followPhoneWidth)
const ownTab = computed(() => !props.embedded || phone.value)
const actionsOpen = ref(false)
const actionClass = computed(() =>
  phone.value
    ? 'flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-slate-300 hover:bg-slate-700'
    : 'btn-icon',
)

function closeColumn(): void {
  window.dispatchEvent(new CustomEvent(COLUMN_CLOSE_EVENT))
}

// The workspace's fullscreen: terminal and input field only.
const fullscreen = ref(false)
const followFullscreen = (event: Event): void => {
  fullscreen.value = (event as CustomEvent<boolean>).detail
}
window.addEventListener(COLUMN_FULLSCREEN_EVENT, followFullscreen)

const terminal = new Terminal({
  fontSize: fontSize.value,
  lineHeight: lineHeight.value,
  fontFamily: TERMINAL_FONTS[terminalFont.value],
  cursorBlink: true,
  scrollback: SCROLLBACK_LINES,
  // The unicode API of the addon below is still marked as proposed.
  allowProposedApi: true,
  theme: {
    background: '#0f172a',
    foreground: '#f1f5f9',
    cursor: '#ef4444',
    selectionBackground: '#7f1d1d',
  },
})
const fit = new FitAddon()
terminal.loadAddon(fit)
// Plain web addresses in the output become links (Claude's own OSC 8 links work without it).
terminal.loadAddon(new WebLinksAddon())
// Files and folders the agent mentions open with a click (only those that exist).
registerFileLinks(terminal, router, () => session.value?.path)
// What an agent copies (OSC 52, e.g. Claude Code's copy) lands in the browser's clipboard.
terminal.loadAddon(new ClipboardAddon())
// Emoji are two cells wide in the agents' output; xterm's default (Unicode 6) counts one and
// shifts every following character.
terminal.loadAddon(new Unicode11Addon())
terminal.unicode.activeVersion = '11'
let socket: WebSocket | null = null
const resizeObserver = new ResizeObserver(() => fit.fit())

// Scrolling: the agents run full screen and catch the mouse themselves (Claude Code scrolls one
// line per wheel report), and browsers report a wheel notch in different sizes (Firefox lines,
// Chrome pixels), which xterm.js turns into different numbers of reports. So every notch and
// every swipe step becomes exactly the user's number of single-line wheel events.
const { scrollLines } = useSettings()

// Settings changed here or in another column take effect at once.
watch([fontSize, lineHeight, terminalFont], async ([size, height, font]) => {
  await loadFont(font, size)
  terminal.options.fontSize = size
  terminal.options.lineHeight = height
  terminal.options.fontFamily = TERMINAL_FONTS[font]
  fit.fit()
})

/** xterm.js measures the characters once: the font must be loaded before it does. */
async function loadFont(font: TerminalFont, size: number): Promise<void> {
  // The GPU renderer keeps each drawn glyph: a symbol drawn before its font arrived would
  // stay a box, so the fonts load (for their symbols too) before the terminal draws.
  await document.fonts.load(`${size}px ${TERMINAL_FONTS[font]}`, FONT_SAMPLE)
}
// Events dispatched here pass the wheel handler below untouched.
const ownWheelEvents = new WeakSet<Event>()

/** Scroll by single-line wheel events; x and y place them on the terminal. */
function scrollLinesBy(lines: number, x: number, y: number): void {
  const element = terminal.element
  if (!element) return
  for (let index = 0; index < Math.abs(lines); index++) {
    const event = new WheelEvent('wheel', {
      deltaY: Math.sign(lines),
      deltaMode: WheelEvent.DOM_DELTA_LINE,
      clientX: x,
      clientY: y,
      bubbles: true,
      cancelable: true,
    })
    ownWheelEvents.add(event)
    element.dispatchEvent(event)
  }
}

/** A wheel notch or swipe step scrolls the user's number of lines. */
function scrollTerminal(steps: number, x: number, y: number): void {
  scrollLinesBy(steps * scrollLines.value, x, y)
}

/** The jog scroller sends lines directly; they land in the middle of the terminal. */
function onJog(lines: number): void {
  const box = container.value?.getBoundingClientRect()
  if (box) scrollLinesBy(lines, box.left + box.width / 2, box.top + box.height / 2)
}

function onWheel(event: WheelEvent): void {
  if (ownWheelEvents.has(event) || event.deltaY === 0) return
  event.preventDefault()
  event.stopPropagation()
  scrollTerminal(Math.sign(event.deltaY), event.clientX, event.clientY)
}

// xterm.js does not pass finger swipes on, so swipes (and their glide after a flick) become
// wheel events too. Taps stay untouched.
// In a workspace column, a sideways swipe brings the neighbouring column (WorkspaceView).
const touchScroll = useTouchScroll(
  scrollTerminal,
  props.embedded
    ? (direction) => window.dispatchEvent(new CustomEvent(COLUMN_SWIPE_EVENT, { detail: direction }))
    : undefined,
)

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

function submitText(text: string): void {
  if (!settings.value) return
  sendInput(text)
  // Enter separately, so the agent sees typed text plus submit, not one pasted block.
  window.setTimeout(() => sendInput('\r'), settings.value.submit_delay_ms)
}


const NORMAL_CLOSURE = 1000
const FIRST_APPLICATION_CODE = 4000
const RECONNECT_MILLISECONDS = 2000
const reconnecting = ref(false)
let reconnectTimer: number | undefined
let unmounted = false

function connect(): void {
  window.clearTimeout(reconnectTimer)
  socket = new WebSocket(terminalUrl(props.id, terminal.cols, terminal.rows))
  socket.binaryType = 'arraybuffer'
  socket.onopen = () => {
    connected.value = true
    reconnecting.value = false
    // Typing goes to our input field first: dictation tools (and phone keyboards) work there,
    // not in the terminal's own input. In the workspace only the active column takes the focus.
    if (!props.embedded || window.frameElement?.getAttribute('data-active') === 'true') {
      messageInput.value?.focus()
    }
  }
  socket.onmessage = (event: MessageEvent<ArrayBuffer>) => terminal.write(new Uint8Array(event.data))
  socket.onclose = (event: CloseEvent) => {
    connected.value = false
    // Closed on purpose by the server: the session ended (1000) or may not be shown (4000 and
    // up, see api.py). Anything else means the connection went away while the agent runs on,
    // e.g. Agent-Orc restarted after an update (1012, terminal.py) or a lost network: then it
    // comes back by itself.
    if (!unmounted && event.code !== NORMAL_CLOSURE && event.code < FIRST_APPLICATION_CODE) {
      reconnecting.value = true
      reconnectTimer = window.setTimeout(connect, RECONNECT_MILLISECONDS)
    }
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
  await loadFont(terminalFont.value, fontSize.value)
  terminal.open(container.value)
  // The GPU renderer draws box and block characters itself (customGlyphs), so the agents'
  // frames stay closed with any font and line spacing; the DOM renderer takes them from the
  // font. If the browser takes the graphics context away (driver reset, too many contexts),
  // xterm.js advises dropping the addon: the terminal then draws with its DOM renderer again.
  const webgl = new WebglAddon()
  webgl.onContextLoss(() => webgl.dispose())
  terminal.loadAddon(webgl)
  fit.fit()
  resizeObserver.observe(container.value)
  // Capture phase: the notch is resized before xterm.js sees it.
  container.value.addEventListener('wheel', onWheel, { capture: true, passive: false })
  container.value.addEventListener('touchstart', touchScroll.onTouchStart, { passive: true })
  // Not passive: a swipe must not also scroll or zoom the page.
  container.value.addEventListener('touchmove', touchScroll.onTouchMove, { passive: false })
  container.value.addEventListener('touchend', touchScroll.onTouchEnd, { passive: true })
  connect()
})

onBeforeUnmount(() => {
  PHONE_WIDTH.removeEventListener('change', followPhoneWidth)
  window.removeEventListener(COLUMN_FULLSCREEN_EVENT, followFullscreen)
  unmounted = true
  window.clearTimeout(reconnectTimer)
  touchScroll.stopGlide()
  resizeObserver.disconnect()
  socket?.close()
  terminal.dispose()
})
</script>

<template>
  <div class="flex h-dvh flex-col bg-slate-900">
    <!-- Compact buttons on phones, so name and all buttons fit in one row. -->
    <header
      v-if="!fullscreen"
      class="flex items-center gap-1 border-b border-slate-600 px-1 py-1 max-md:[&_.btn-icon]:size-8"
    >
      <button
        v-if="!embedded"
        class="btn-icon"
        :aria-label="$t('terminal.back')"
        @click="router.push('/sessions')"
      >
        <AppIcon name="up" class="-rotate-90" />
      </button>
      <!-- State on the left, the buttons acting on the agent on the right. -->
      <ContextMeter
        v-if="session && session.context_tokens != null && session.context_window != null"
        compact
        :tokens="session.context_tokens"
        :window="session.context_window"
      />
      <!-- Embedded in the workspace, the column's tab names the agent already (not on phones). -->
      <!-- In the light bulb's amber, set off from the usage figure. -->
      <h1 class="ml-2 min-w-0 flex-1 truncate font-semibold text-amber-300">{{ ownTab ? name : '' }}</h1>
      <!-- The actions: side by side on computers, behind ⋯ on phones so the name has room. -->
      <div class="relative flex items-center">
        <button
          v-if="phone"
          class="btn-icon"
          :aria-label="$t('terminal.actions')"
          :title="$t('terminal.actions')"
          @click="actionsOpen = !actionsOpen"
        >
          <AppIcon name="more" />
        </button>
        <div v-if="phone && actionsOpen" class="fixed inset-0 z-30" @click="actionsOpen = false" />
        <div
          v-if="!phone || actionsOpen"
          :class="
            phone
              ? 'card absolute top-full right-0 z-40 mt-1 flex w-60 flex-col p-1 shadow-xl'
              : 'flex items-center gap-1'
          "
        >
          <RestartButton v-if="session?.running" :session="session" :button-class="actionClass" :with-label="phone" />
          <TerminalButton
            v-if="session && !session.terminal"
            :path="session.path"
            :agent-id="session.id"
            :button-class="actionClass"
            :with-label="phone"
          />
          <!-- The agent's project in the file view; in the workspace within the column (back
               returns). -->
          <RouterLink
            v-if="session"
            :to="{ path: '/files', query: { path: session.path } }"
            :class="actionClass"
            :aria-label="$t('terminal.files')"
            :title="$t('terminal.files')"
          >
            <AppIcon name="folder" /><span v-if="phone">{{ $t('terminal.files') }}</span>
          </RouterLink>
          <!-- What the agent changed; in the workspace it opens within the column (back returns). -->
          <RouterLink
            :to="`/changes/${encodeURIComponent(id)}`"
            :class="actionClass"
            :aria-label="$t('changes.open')"
            :title="$t('changes.open')"
          >
            <AppIcon name="diff" /><span v-if="phone">{{ $t('changes.button') }}</span>
          </RouterLink>
          <button
            :class="actionClass"
            :aria-label="$t('terminal.plainText')"
            :title="$t('terminal.plainText')"
            @click="((actionsOpen = false), showPlainText())"
          >
            <AppIcon name="copy" /><span v-if="phone">{{ $t('terminal.plainText') }}</span>
          </button>
          <!-- The device's font size (the settings menu holds it too). -->
          <div v-if="phone" class="flex items-center gap-2 px-3 py-1 text-sm text-slate-300">
            <span class="flex-1">{{ $t('settings.fontSize') }}</span>
            <button class="btn-icon size-8" :aria-label="$t('settings.less')" @click="stepFontSize(-1)">−</button>
            <span class="w-6 text-center">{{ fontSize }}</span>
            <button class="btn-icon size-8" :aria-label="$t('settings.more')" @click="stepFontSize(1)">+</button>
          </div>
        </div>
      </div>
      <button v-if="embedded && phone" class="btn-icon" :aria-label="$t('workspace.close')" :title="$t('workspace.close')" @click="closeColumn">
        ×
      </button>
    </header>

    <div v-if="plainText !== null" class="fixed inset-0 z-40 flex flex-col bg-slate-900">
      <header class="flex items-center gap-2 border-b border-slate-800 px-2 py-1">
        <h2 class="flex-1 font-semibold">{{ $t('terminal.plainText') }}</h2>
        <button class="btn-primary min-h-10 px-3" @click="copyPlainText">{{ $t('terminal.copyAll') }}</button>
        <button class="btn-secondary min-h-10 px-3" @click="plainText = null">{{ $t('terminal.close') }}</button>
      </header>
      <pre
        ref="plainTextBox"
        class="flex-1 overflow-auto p-3 font-mono whitespace-pre-wrap break-words text-slate-200 select-text"
        :style="{ fontSize: `${fontSize}px` }"
        >{{ plainText }}</pre
      >
    </div>

    <div class="relative flex min-h-0 flex-1 pt-1 pl-1">
      <div ref="container" class="h-full min-w-0 flex-1" />
      <JogScroller @scroll="onJog" />
      <div
        v-if="!connected"
        class="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-slate-900/85"
      >
        <p class="text-slate-300">
          {{ $t(reconnecting ? 'terminal.reconnecting' : 'terminal.disconnected') }}
        </p>
        <button v-if="!reconnecting" class="btn-primary" @click="connect">{{ $t('terminal.reconnect') }}</button>
      </div>
    </div>

    <MessageInput ref="messageInput" :session-id="id" @submit="submitText" />

    <KeyBar
      v-if="settings && !fullscreen"
      :rows="settings.keys"
      :active="modifiers"
      @send="(sequence) => sendInput(withModifiers(sequence))"
      @submit="submitText"
      @toggle="toggleModifier"
    />
  </div>
</template>
