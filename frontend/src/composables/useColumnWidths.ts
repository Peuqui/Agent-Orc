import { computed, type Ref, ref } from 'vue'
import type { Workspace } from '../api'
import { MIN_VISIBLE } from './useWorkspaceTab'

// The widths of a workspace's columns: N of them fill the screen, a column's right divider makes
// it wider or narrower (mouse or finger), a double click or the reset button makes it equal again.
// On a phone every column fills the screen; the widths set on a computer stay as they are for it.
// Narrowest and widest column a divider can set, as a share of the screen width.
const MIN_WIDTH_SHARE = 0.1
const MAX_WIDTH_SHARE = 1

interface Resize {
  id: string
  pointerId: number
  startX: number
  startShare: number
}

export function useColumnWidths(workspace: Ref<Workspace>, phone: Ref<boolean>, row: Ref<HTMLElement | undefined>) {
  // The divider being dragged; the workspace is stored once it is let go.
  const resize = ref<Resize | null>(null)

  function widthShare(id: string): number {
    if (phone.value) return 1
    return workspace.value.widths[id] ?? 1 / workspace.value.visible
  }

  const gridStyle = computed(() => ({
    gridTemplateColumns: workspace.value.tabs.map((id) => `calc(100cqw * ${widthShare(id)})`).join(' '),
  }))

  /** Sets the width of all columns: N of them fill the screen; individual widths are dropped. */
  function changeVisible(delta: number): void {
    workspace.value.visible = Math.max(MIN_VISIBLE, workspace.value.visible + delta)
    workspace.value.widths = {}
  }

  /** Back to equal columns: the ones dragged wider or narrower return to the default. */
  function resetWidths(): void {
    workspace.value.widths = {}
  }

  function resetWidth(id: string): void {
    delete workspace.value.widths[id]
  }

  function onDividerPointerDown(event: PointerEvent, id: string): void {
    if (event.button !== 0) return
    resize.value = { id, pointerId: event.pointerId, startX: event.clientX, startShare: widthShare(id) }
    const divider = event.currentTarget as HTMLElement
    divider.setPointerCapture(event.pointerId)
  }

  function onDividerPointerMove(event: PointerEvent): void {
    const current = resize.value
    const screenWidth = row.value?.clientWidth
    if (current === null || event.pointerId !== current.pointerId || !screenWidth) return
    const share = current.startShare + (event.clientX - current.startX) / screenWidth
    workspace.value.widths[current.id] = Math.min(MAX_WIDTH_SHARE, Math.max(MIN_WIDTH_SHARE, share))
  }

  function endResize(): void {
    resize.value = null
  }

  return { resize, gridStyle, changeVisible, resetWidths, resetWidth, onDividerPointerDown, onDividerPointerMove, endResize }
}
