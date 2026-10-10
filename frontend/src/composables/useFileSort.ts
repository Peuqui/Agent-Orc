import { ref } from 'vue'
import { clicked, formatSort, parseSort, type SortKey } from '../fileSort'

// How the lists are ordered: one for all of them, kept in this browser.
const SORT_STORAGE_KEY = 'agent-orc-files-sort'
const sort = ref(parseSort(localStorage.getItem(SORT_STORAGE_KEY)))

function sortBy(key: SortKey): void {
  sort.value = clicked(sort.value, key)
  localStorage.setItem(SORT_STORAGE_KEY, formatSort(sort.value))
}

export function useFileSort() {
  return { sort, sortBy }
}
