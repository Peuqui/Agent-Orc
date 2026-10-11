import { computed, type Ref, ref } from 'vue'
import type { Workspace } from '../api'
import { boundaryShift } from './boundaryShift'
import { MIN_VISIBLE } from './useWorkspaceTab'

// The widths of a workspace's columns: N of them fill the screen. A divider sits between two
// neighbours and only moves their boundary (mouse or finger): what one gains the other loses, so
// the width of all columns together stays. A double click on a divider or the reset button makes
// the columns equal again. On a phone every column fills the screen; the widths set on a computer
// stay as they are for it.

interface Resize {
  // The column left of the dragged divider; its right neighbour is the other one that changes.
  id: string
  neighbourId: string
  pointerId: number
  startX: number
  startShare: number
  startNeighbourShare: number
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

  /** The column right of `id`, the other one a divider between them changes. */
  function neighbourOf(id: string): string | undefined {
    return workspace.value.tabs[workspace.value.tabs.indexOf(id) + 1]
  }

  /** Back to equal columns: the ones dragged wider or narrower return to the default. */
  function resetWidths(): void {
    workspace.value.widths = {}
  }

  /** Equal again for the two columns beside the divider right of `id`. */
  function resetWidth(id: string): void {
    delete workspace.value.widths[id]
    const neighbourId = neighbourOf(id)
    if (neighbourId !== undefined) delete workspace.value.widths[neighbourId]
  }

  function onDividerPointerDown(event: PointerEvent, id: string): void {
    if (event.button !== 0) return
    const neighbourId = neighbourOf(id)
    if (neighbourId === undefined) return
    resize.value = {
      id,
      neighbourId,
      pointerId: event.pointerId,
      startX: event.clientX,
      startShare: widthShare(id),
      startNeighbourShare: widthShare(neighbourId),
    }
    const divider = event.currentTarget as HTMLElement
    divider.setPointerCapture(event.pointerId)
  }

  function onDividerPointerMove(event: PointerEvent): void {
    const current = resize.value
    const screenWidth = row.value?.clientWidth
    if (current === null || event.pointerId !== current.pointerId || !screenWidth) return
    const shift = boundaryShift(
      current.startShare,
      current.startNeighbourShare,
      (event.clientX - current.startX) / screenWidth,
    )
    workspace.value.widths[current.id] = current.startShare + shift
    workspace.value.widths[current.neighbourId] = current.startNeighbourShare - shift
  }

  function endResize(): void {
    resize.value = null
  }

  return { resize, gridStyle, changeVisible, resetWidths, resetWidth, onDividerPointerDown, onDividerPointerMove, endResize }
}
