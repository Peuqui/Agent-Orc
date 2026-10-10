/** What the file list puts into a drag: the paths dragged (the selection, or the one row), as a
 * JSON list. Dropped on a folder, a list or the trash panel they are moved there. */
export const DRAG_PATH_TYPE = 'application/x-agent-orc-path'

export function setDraggedPaths(event: DragEvent, paths: string[]): void {
  if (!event.dataTransfer) return
  event.dataTransfer.setData(DRAG_PATH_TYPE, JSON.stringify(paths))
  event.dataTransfer.effectAllowed = 'copyMove'
}

/** The paths of a drag of the file list; none for any other drag. */
export function draggedPaths(event: DragEvent): string[] {
  const text = event.dataTransfer?.getData(DRAG_PATH_TYPE)
  return text ? (JSON.parse(text) as string[]) : []
}

/** Whether a drag carries paths of the file list (all a drag over shows: its data is secret until
 * the drop). */
export function dragsPaths(event: DragEvent): boolean {
  return event.dataTransfer?.types.includes(DRAG_PATH_TYPE) ?? false
}
