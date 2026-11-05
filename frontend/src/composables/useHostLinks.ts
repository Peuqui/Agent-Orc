import { useRouter, type RouteLocationRaw } from 'vue-router'
import { currentHost, rootAddress } from '../api'
import { hostPath } from '../hostPaths'

/** The address of a page of the app of `host` (another machine's, served below /hosts/<name>/
 * by this one), or of this machine's own app for null. Another machine's page than this one is
 * reached by an address, not by the router. */
export function useHostLinks(host: string | null) {
  const router = useRouter()

  function href(route: RouteLocationRaw): string {
    if (host === currentHost) return router.resolve(route).href
    const page = host === null ? rootAddress() : hostPath(new URL(rootAddress()).pathname, host)
    return `${page}#${router.resolve(route).fullPath}`
  }

  /** Goes to the page: within this app by the router, to another machine's by its address. */
  async function go(route: RouteLocationRaw): Promise<void> {
    if (host === currentHost) await router.push(route)
    else window.location.assign(href(route))
  }

  return { href, go }
}
