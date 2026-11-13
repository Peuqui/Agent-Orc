// What a file is shown as, by its extension: text in the editor (Markdown and HTML also as a
// page), a picture, a sound or a video the browser plays, a PDF or a Word document drawn here.
// Anything else is tried as text; what is not text is only offered to download ('binary').
export type FileKind = 'text' | 'markdown' | 'html' | 'pdf' | 'docx' | 'image' | 'audio' | 'video' | 'binary'

const KIND_OF_EXTENSION: Record<string, FileKind> = {
  md: 'markdown',
  markdown: 'markdown',
  html: 'html',
  htm: 'html',
  pdf: 'pdf',
  docx: 'docx',
  ...Object.fromEntries(['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'ico', 'avif'].map((name) => [name, 'image'])),
  ...Object.fromEntries(['wav', 'mp3', 'ogg', 'oga', 'opus', 'flac', 'm4a', 'aac'].map((name) => [name, 'audio'])),
  ...Object.fromEntries(['mp4', 'webm', 'ogv', 'mov'].map((name) => [name, 'video'])),
}

export function kindOfFile(fileName: string): FileKind {
  const dot = fileName.lastIndexOf('.')
  if (dot <= 0) return 'text'
  return KIND_OF_EXTENSION[fileName.slice(dot + 1).toLowerCase()] ?? 'text'
}

/** Kinds whose text is edited here; Markdown and HTML can also be shown as a page. */
export function isTextKind(kind: FileKind): boolean {
  return kind === 'text' || kind === 'markdown' || kind === 'html'
}
