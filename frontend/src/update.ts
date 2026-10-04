// A new service worker normally takes over at once (skipWaiting); one seen stuck in "waiting"
// (Chrome) is given this long.
const TAKEOVER_TIMEOUT_MS = 5000

/**
 * Switch to the installed new version. Asked for an update, the service worker may bring a new
 * one; the page reloads once it has taken over, so the new worker serves the new files. A new
 * worker that does not take over in time is bypassed: the old one is unregistered and the page
 * loads straight from the server, where the new worker then registers afresh. Without a new
 * worker nothing cached stands in the way of a plain reload. Used for a newly installed version
 * and when a part of the old one is gone.
 */
export async function reloadToNewVersion(): Promise<void> {
  const registration = await navigator.serviceWorker?.getRegistration()
  try {
    await registration?.update()
  } catch {
    // The worker script is briefly missing while a version is being installed: reload anyway;
    // a page that still gets the old version notices the new one again and comes back here.
    location.reload()
    return
  }
  if (registration && (registration.installing || registration.waiting)) {
    navigator.serviceWorker.addEventListener('controllerchange', () => location.reload(), { once: true })
    window.setTimeout(async () => {
      await registration.unregister()
      location.reload()
    }, TAKEOVER_TIMEOUT_MS)
  } else {
    location.reload()
  }
}
