import { onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { jumpToWorkspace } from './useWorkspaceTab'

// Desktop shortcuts: Alt+Shift+1…9 goes to that column, Alt+Shift+←/→ to the previous or next
// workspace. Ctrl+digits cannot be used: the browser keeps them for its own tabs.
const COLUMN_KEYS = ['Digit1', 'Digit2', 'Digit3', 'Digit4', 'Digit5', 'Digit6', 'Digit7', 'Digit8', 'Digit9']
const WORKSPACE_STEPS: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1 }

/** Listens on this page; the returned handler also goes on each column's page, where typing
 * mostly happens (its shortcuts are caught there, before the terminal). */
export function useWorkspaceKeys(options: {
  tabs: () => string[]
  // The workspaces as the bar shows them, and the one shown.
  order: () => (string | null)[]
  name: () => string | null
  goToColumn: (id: string) => void
}): (event: KeyboardEvent) => void {
  const router = useRouter()

  function onShortcut(event: KeyboardEvent): void {
    if (!event.altKey || !event.shiftKey || event.ctrlKey || event.metaKey) return
    // The key's place, not its character: Shift turns "1" into "!" (layouts differ).
    const column = COLUMN_KEYS.indexOf(event.code)
    const step = WORKSPACE_STEPS[event.code]
    if (column >= 0) {
      const id = options.tabs()[column]
      if (id === undefined) return
      event.preventDefault()
      options.goToColumn(id)
    } else if (step !== undefined) {
      const order = options.order()
      if (order.length < 2) return
      event.preventDefault()
      // As the bar shows them, going round at the ends.
      const here = order.indexOf(options.name())
      jumpToWorkspace(router, order[(here + step + order.length) % order.length])
    }
  }

  window.addEventListener('keydown', onShortcut, true)
  onBeforeUnmount(() => window.removeEventListener('keydown', onShortcut, true))
  return onShortcut
}
