import { ref } from 'vue'
import { api } from '../api'

// Push messages need a service worker and the Push API, both only in a secure context (HTTPS or
// localhost); iPhones offer them only to the app installed on the home screen.
export const pushSupported =
  window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window

/** This device receives Agent-Orc's push messages. */
const subscribed = ref(false)

async function currentSubscription(): Promise<PushSubscription | null> {
  const registration = await navigator.serviceWorker.ready
  return registration.pushManager.getSubscription()
}

/** The Push API takes the server key as raw bytes; the server sends it base64url-encoded. */
function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/')
  return Uint8Array.from(atob(base64), (character) => character.charCodeAt(0))
}

/** Looks up this device's subscription and hands it to the server again (it may have lost it). */
async function refresh(): Promise<void> {
  if (!pushSupported) return
  const subscription = await currentSubscription()
  subscribed.value = subscription !== null
  if (subscription) await api.subscribePush(subscription.toJSON())
}

/** Ask for permission and subscribe; false if the user refused notifications. */
async function enable(): Promise<boolean> {
  if ((await Notification.requestPermission()) !== 'granted') return false
  const registration = await navigator.serviceWorker.ready
  const { key } = await api.pushKey()
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: keyBytes(key),
  })
  await api.subscribePush(subscription.toJSON())
  subscribed.value = true
  return true
}

async function disable(): Promise<void> {
  const subscription = await currentSubscription()
  if (subscription) {
    await api.unsubscribePush(subscription.endpoint)
    await subscription.unsubscribe()
  }
  subscribed.value = false
}

export function usePush() {
  return { subscribed, refresh, enable, disable }
}
