// What an upload of files and folders needs apart from the page: the files of a dropped folder
// with the folder each lies in, and the names a dropped folder takes where its own is taken.

export interface UploadItem {
  /** The file; none for an empty folder that is only to be made. */
  file: File | null
  /** The folder below the open one it goes into ("" for the open one itself). */
  directory: string
}

function readEntries(reader: FileSystemDirectoryReader): Promise<FileSystemEntry[]> {
  return new Promise((resolve, reject) => reader.readEntries(resolve, reject))
}

/** The files of a dropped file or folder, with the folder each lies in (`parent` holds the entry);
 * a folder with nothing in it counts as an item without a file, so it is made, too. */
export async function collect(entry: FileSystemEntry, parent: string): Promise<UploadItem[]> {
  if (entry.isFile) {
    const file = await new Promise<File>((resolve, reject) => (entry as FileSystemFileEntry).file(resolve, reject))
    return [{ file, directory: parent }]
  }
  const reader = (entry as FileSystemDirectoryEntry).createReader()
  const inside: FileSystemEntry[] = []
  // A reader gives its entries in batches (up to 100) until it gives none.
  for (let batch = await readEntries(reader); batch.length > 0; batch = await readEntries(reader)) {
    inside.push(...batch)
  }
  const directory = parent ? `${parent}/${entry.name}` : entry.name
  if (inside.length === 0) return [{ file: null, directory }]
  return (await Promise.all(inside.map((child) => collect(child, directory)))).flat()
}

/** `name`, or "name-2", "name-3" ... when it is taken. */
export function freeName(name: string, taken: Set<string>): string {
  let candidate = name
  for (let number = 2; taken.has(candidate); number += 1) candidate = `${name}-${number}`
  return candidate
}

/** The items with each folder dropped at the top under a name that is free in `takenNames`: a
 * folder whose name is taken becomes "name-2", it is not mixed into the one that is there. */
export function renameTakenFolders(items: UploadItem[], takenNames: Iterable<string>): UploadItem[] {
  const taken = new Set(takenNames)
  const renamed = new Map<string, string>()
  return items.map((item) => {
    if (!item.directory) return item
    const [top = '', ...below] = item.directory.split('/')
    if (!renamed.has(top)) {
      const free = freeName(top, taken)
      taken.add(free)
      renamed.set(top, free)
    }
    return { ...item, directory: [renamed.get(top), ...below].join('/') }
  })
}
