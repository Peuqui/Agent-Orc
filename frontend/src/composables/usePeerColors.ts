import { type InjectionKey, type Ref, inject, provide } from 'vue'
import { MACHINE_COLOR } from '../peerConversations'

// The conversations page gives every agent its colour (colorsOf); the bubbles, rows and lanes
// below it take it from here instead of having it handed down through each of them.
const KEY: InjectionKey<Ref<Map<string, string>>> = Symbol('peerColors')

/** A peer's colour class; one not among the lanes (yet) gets the machines' grey. */
function lookup(colors: Ref<Map<string, string>>): (name: string) => string {
  return (name) => colors.value.get(name) ?? MACHINE_COLOR
}

/** Hands the colours to the components below; the page itself looks them up with the result. */
export function providePeerColors(colors: Ref<Map<string, string>>): (name: string) => string {
  provide(KEY, colors)
  return lookup(colors)
}

export function usePeerColor(): (name: string) => string {
  return lookup(inject(KEY)!)
}
