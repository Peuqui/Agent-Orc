import { computed, reactive, type WritableComputedRef } from 'vue'

// The unsent text of each agent's message field survives a reload (e.g. when a new version is
// installed), per agent and tab. Kept here so other parts of the page, like the dialog that
// sends a prompt to several agents, can put text into a field that is not even shown.
const KEY_PREFIX = 'agent-orc-draft:'
const drafts = reactive<Record<string, string>>({})

function load(sessionId: string): void {
  if (!(sessionId in drafts)) drafts[sessionId] = sessionStorage.getItem(KEY_PREFIX + sessionId) ?? ''
}

function setDraft(sessionId: string, text: string): void {
  drafts[sessionId] = text
  if (text) sessionStorage.setItem(KEY_PREFIX + sessionId, text)
  else sessionStorage.removeItem(KEY_PREFIX + sessionId)
}

export function draftOf(sessionId: string): WritableComputedRef<string> {
  load(sessionId)
  return computed({ get: () => drafts[sessionId], set: (text) => setDraft(sessionId, text) })
}

/** Below what the field already holds, as a template is. */
export function addToDraft(sessionId: string, text: string): void {
  load(sessionId)
  setDraft(sessionId, drafts[sessionId] ? `${drafts[sessionId]}\n${text}` : text)
}

/** Read the draft afresh: the page at the top of the tab put a dictation into it. */
export function reloadDraft(sessionId: string): void {
  drafts[sessionId] = sessionStorage.getItem(KEY_PREFIX + sessionId) ?? ''
}

/** After what the field holds, as a dictation is. Read afresh: the page at the top of the tab puts in
 * a dictation for a column that was closed meanwhile, whose field was typed into on its own page. */
export function appendDictated(sessionId: string, text: string): void {
  const held = sessionStorage.getItem(KEY_PREFIX + sessionId) ?? ''
  setDraft(sessionId, held ? `${held} ${text}` : text)
}
