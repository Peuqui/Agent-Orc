// Another machine's Agent-Orc is served by this one below /hosts/<name>/, and its page then runs
// there: every address it builds is relative to it, so nothing else has to know. These tell which
// machine a page belongs to, and where this machine's own app is.
const HOST_SEGMENT = /\/hosts\/([^/]+)\/$/

/** The machine the page at `pathname` belongs to; null for this machine's own app. */
export function hostOf(pathname: string): string | null {
  const match = HOST_SEGMENT.exec(pathname)
  return match ? decodeURIComponent(match[1]!) : null
}

/** The path of this machine's own app, from a page of it or of another machine's. */
export function rootOf(pathname: string): string {
  return pathname.replace(HOST_SEGMENT, '/')
}

/** The path of another machine's app, from a page of this machine's own. */
export function hostPath(pathname: string, name: string): string {
  return `${rootOf(pathname)}hosts/${encodeURIComponent(name)}/`
}

/** The section of the page at `hash` ("#/files?path=/x" is "/files") if `sections` has it, else
 * `fallback`: what another machine can show alike, as it has no such folder, agent or workspace. */
export function sectionOf(hash: string, sections: string[], fallback: string): string {
  const section = hash.replace(/^#/, '').split('?')[0]!
  return sections.includes(section) ? section : fallback
}
