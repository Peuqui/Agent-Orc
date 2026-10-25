// Claude Code's offers to stop asking ("Yes, and don't ask again for ..."), as its PermissionRequest
// hook sends them (permission update entries). Pure, so it can be tested without a browser.

export type SuggestionDestination = 'session' | 'localSettings' | 'projectSettings' | 'userSettings'

export interface PermissionRule {
  toolName: string
  ruleContent?: string
}

export interface PermissionSuggestion {
  type: string
  destination: SuggestionDestination
  rules?: PermissionRule[]
  behavior?: string
  mode?: string
  directories?: string[]
}

/** What a suggestion would allow from now on, as Claude Code writes rules: `Bash(git push:*)`. */
export type SuggestionText =
  | { kind: 'rules'; text: string }
  | { kind: 'mode'; mode: string }
  | { kind: 'directories'; text: string }

/** The text for a suggestion the web app offers, or null for one it does not (only what allows more:
 * rules to allow, a mode, folders to add). */
export function suggestionText(suggestion: PermissionSuggestion): SuggestionText | null {
  if (suggestion.type === 'addRules' && suggestion.behavior === 'allow' && suggestion.rules?.length) {
    const rules = suggestion.rules.map((rule) => (rule.ruleContent ? `${rule.toolName}(${rule.ruleContent})` : rule.toolName))
    return { kind: 'rules', text: rules.join(', ') }
  }
  if (suggestion.type === 'setMode' && suggestion.mode) return { kind: 'mode', mode: suggestion.mode }
  if (suggestion.type === 'addDirectories' && suggestion.directories?.length) {
    return { kind: 'directories', text: suggestion.directories.join(', ') }
  }
  return null
}
