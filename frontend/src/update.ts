/**
 * Switch to the installed new version. Asked for an update, the service worker may bring a new
 * one; it takes over by itself (skipWaiting), and the page reloads once it has, so the new
 * worker serves the new files. Without a new worker nothing cached stands in the way of a plain
 * reload. Used for a newly installed version and when a part of the old one is gone.
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
  if (registration?.installing || registration?.waiting) {
    navigator.serviceWorker.addEventListener('controllerchange', () => location.reload(), { once: true })
  } else {
    location.reload()
  }
}
