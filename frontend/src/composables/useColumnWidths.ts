import { computed, type Ref, ref, watch } from 'vue'
import type { Workspace } from '../api'
import { boundaryShift, MAX_VISIBLE } from './boundaryShift'
import { loadColumnWidths, MIN_VISIBLE, saveColumnWidths } from './useWorkspaceTab'

// The widths of a workspace's columns: N of them fill the screen. A divider sits between two
// neighbours and only moves their boundary (mouse or finger): what one gains the other loses, so
// the width of all columns together stays. A double click on a divider or the reset button makes
// the columns equal again. The widths are kept on this device, per workspace (screens differ);
// on a phone every column fills the screen, and the widths set on a computer stay as they are.

interface Resize {
  // The column left of the dragged divider; its right neighbour is the other one that changes.
  id: string
  neighbourId: string
  pointerId: number
  startX: number
  startShare: number
  startNeighbourShare: number
}

export function useColumnWidths(
  name: Ref<string | null>,
  workspace: Ref<Workspace>,
  phone: Ref<boolean>,
  row: Ref<HTMLElement | undefined>,
) {
  // The columns set wider or narrower, by agent, as a share of the screen width.
  const shares = ref<Record<string, number>>({})
  watch(name, (shown) => (shares.value = loadColumnWidths(shown)), { immediate: true })
  watch(shares, () => saveColumnWidths(name.value, shares.value), { deep: true })
  const resized = computed(() => Object.keys(shares.value).length > 0)

  // The divider being dragged.
  const resize = ref<Resize | null>(null)

  function widthShare(id: string): number {
    if (phone.value) return 1
    return shares.value[id] ?? 1 / workspace.value.visible
  }

  const gridStyle = computed(() => ({
    gridTemplateColumns: workspace.value.tabs.map((id) => `calc(100cqw * ${widthShare(id)})`).join(' '),
  }))

  /** Sets the width of all columns: N of them fill the screen; individual widths are dropped. */
  function changeVisible(delta: number): void {
    workspace.value.visible = Math.min(MAX_VISIBLE, Math.max(MIN_VISIBLE, workspace.value.visible + delta))
    shares.value = {}
  }

  /** The column right of `id`, the other one a divider between them changes. */
  function neighbourOf(id: string): string | undefined {
    return workspace.value.tabs[workspace.value.tabs.indexOf(id) + 1]
  }

  /** Back to equal columns: the ones dragged wider or narrower return to the default. */
  function resetWidths(): void {
    shares.value = {}
  }

  /** Equal again for the two columns beside the divider right of `id`. */
  function resetWidth(id: string): void {
    delete shares.value[id]
    const neighbourId = neighbourOf(id)
    if (neighbourId !== undefined) delete shares.value[neighbourId]
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
    shares.value[current.id] = current.startShare + shift
    shares.value[current.neighbourId] = current.startNeighbourShare - shift
  }

  /** Let go: what belongs to agents that are no longer open here is dropped. */
  function endResize(): void {
    resize.value = null
    const open = new Set(workspace.value.tabs)
    shares.value = Object.fromEntries(Object.entries(shares.value).filter(([id]) => open.has(id)))
  }

  return { resize, resized, gridStyle, changeVisible, resetWidths, resetWidth, onDividerPointerDown, onDividerPointerMove, endResize }
}
