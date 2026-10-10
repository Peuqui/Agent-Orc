import { ref } from 'vue'

/**
 * The agents that are in view at the moment (the columns of the open workspace, the cards of the
 * agents page): they show their own requests, so the announcement at the top leaves them out. Set
 * by the page that shows them.
 */
export const shownAgents = ref<string[]>([])
