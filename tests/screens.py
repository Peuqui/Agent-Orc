"""Screens of Claude Code (recorded from version 2.1.325, in a tmux window) for the tests that read
what the agent shows."""

INPUT_FIELD = "─" * 40 + "\n❯ \n" + "─" * 40

# Below the input field: the mode line, then the list of what runs in the background.
SUBAGENTS_SCREEN = (
    "● Fall 2 gestartet.\n"
    "✻ Waiting for 2 background agents to finish\n"
    + INPUT_FIELD
    + "\n  ⏵⏵ auto mode on (shift+tab to cycle) · ↓ to manage"
    "\n  ● main"
    "\n  ◯ general-purpose  Sleep 240 Sekunden (A)            11s · ↓ 11.5k tokens"
    "\n  ◯ general-purpose  Sleep 240 Sekunden (B)            11s · ↓ 11.5k tokens"
)

# ↓ moved into the list: the selected row is led by "❯ " (first the main row, then an agent).
MAIN_SELECTED_SCREEN = (
    "✻ Waiting for 2 background agents to finish\n" + INPUT_FIELD + "\n  ↑/↓ to select"
    "\n❯ ● main"
    "\n  ◯ general-purpose  Agent 1            19s · ↓ 11.5k tokens"
    "\n  ◯ general-purpose  Agent 2            19s · ↓ 11.5k tokens"
)
AGENT_SELECTED_SCREEN = (
    "✻ Waiting for 2 background agents to finish\n"
    + INPUT_FIELD
    + "\n  Enter to view · x to stop · ctrl+x ctrl+k to stop all agents"
    "\n  ● main"
    "\n❯ ◯ general-purpose  Agent 1            20s · ↓ 11.5k tokens"
    "\n  ◯ general-purpose  Agent 2            20s · ↓ 11.5k tokens"
)

# Eight agents: five rows and a count of the rest.
MANY_SUBAGENTS_SCREEN = (
    "✻ Waiting for 8 background agents to finish\n"
    + INPUT_FIELD
    + "\n  ⏵⏵ auto mode on (shift+tab to cycle) · ↓ to manage"
    "\n  ● main"
    + "".join(f"\n  ◯ general-purpose  Agent {n}      13s · ↓ 11.5k tokens" for n in range(1, 6))
    + "\n  ↓ 3 more"
)

# A workflow is one row of its own (and no row of the main agent).
WORKFLOW_SCREEN = (
    "✻ Waiting for 1 dynamic workflow to finish\n"
    + INPUT_FIELD
    + "\n  ⏵⏵ auto mode on (shift+tab to cycle)"
    "\n  ◯ schlaftest  ▰▰▰▰▰▰▰▰▰▰▱▱▱▱▱▱▱▱▱▱  1/2 · 59s · ↓ 20.7k tokens"
)

# Nothing runs any more (the subagents that ended are only offered under /tasks).
NO_SUBAGENTS_SCREEN = (
    "● Alle drei Subagenten sind fertig (OK).\n"
    + INPUT_FIELD
    + "\n  ⏵⏵ auto mode on (shift+tab to cycle) · /tasks to see subagents"
)

# A shell command in the background is no subagent: the mode line only counts it.
BACKGROUND_SHELL_SCREEN = (
    "✻ Crunched for 2s · done 8:05 · 1 shell still running\n"
    + INPUT_FIELD
    + "\n  ⏵⏵ auto mode on · 1 shell · ↓ to manage"
)

# The same row in the conversation above the input field is no list of running agents.
ROW_IN_CONVERSATION_SCREEN = (
    "  ◯ general-purpose  Agent 1            19s · ↓ 11.5k tokens\n"
    + INPUT_FIELD
    + "\n  ⏵⏵ auto mode on (shift+tab to cycle)"
)

# The trust question at the very start: no input field yet.
TRUST_QUESTION_SCREEN = (
    "─" * 40 + "\n Accessing workspace:\n"
    "Quick safety check: Is this a project you created or one you trust?\n"
    "❯ No, exit\n"
    "  Yes, I trust this folder\n"
    "Enter to confirm · Esc to cancel"
)
