/**
 * Switch to the installed new version: a new service worker takes over and reloads the page by
 * itself (registerType autoUpdate); without a new one nothing cached stands in the way of a plain
 * reload. Used by the update banner and when a part of the old version is gone from the server.
 */
export async function reloadToNewVersion(): Promise<void> {
  const registration = await navigator.serviceWorker?.getRegistration()
  await registration?.update()
  if (!registration?.installing && !registration?.waiting) location.reload()
}
