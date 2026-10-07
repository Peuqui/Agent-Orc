import { ref } from 'vue'

/**
 * The agents whose pages are in view at the moment (the columns of the open workspace): they show
 * their own requests, so the announcement at the top leaves them out. Set by the workspace page.
 */
export const shownAgents = ref<string[]>([])
