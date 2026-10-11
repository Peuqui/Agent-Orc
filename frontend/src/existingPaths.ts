import { api } from './api'
import { createPathLookup } from './pathLookup'

/** Of the paths, those that exist in the folder `base` (an agent's): the one lookup of all views. */
export const existingPaths = createPathLookup((base, candidates) => api.existingPaths(base, candidates))
