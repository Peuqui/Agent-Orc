/**
 * Several files chosen or pasted at once go in one after the other: each is stored and put in
 * place before the next starts, so they keep their order (and a note's cursor has moved on).
 */
export async function attachInOrder(files: File[], attach: (file: File) => Promise<void>): Promise<void> {
  for (const file of files) await attach(file)
}
