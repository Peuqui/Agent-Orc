// Push messages from Agent-Orc (push.py): an agent finished its answer, waits for the user, hit
// its usage limit, ...
// Loaded into the generated service worker (vite.config.ts, workbox importScripts). The service
// worker cannot read the app's language setting, so it follows the browser's language.
const PUSH_TEXTS = {
  de: {
    done: '{folder} ist fertig',
    waiting: '{folder} wartet auf dich',
    test: 'Benachrichtigungen sind eingerichtet',
    handover: '{folder}: Übergabe empfohlen',
    limited: '{folder}: Limit erreicht',
    unsent: '{folder}: geplanter Prompt nicht gesendet',
  },
  en: {
    done: '{folder} is done',
    waiting: '{folder} is waiting for you',
    test: 'Notifications are set up',
    handover: '{folder}: handover advised',
    limited: '{folder}: usage limit reached',
    unsent: '{folder}: scheduled prompt not sent',
  },
}

self.addEventListener('push', (event) => {
  const message = event.data.json()
  const texts = navigator.language.toLowerCase().startsWith('de') ? PUSH_TEXTS.de : PUSH_TEXTS.en
  const title = texts[message.kind].replace('{folder}', message.folder)
  event.waitUntil(
    self.registration.showNotification(title, {
      body: message.text,
      icon: 'pwa-192x192.png',
      // One notification per agent: a newer one replaces the older, and still alerts.
      tag: message.session || message.kind,
      renotify: true,
      data: { session: message.session },
    }),
  )
})

// A tap opens the agent in the workspace, in an app window that is already open if there is one.
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const session = event.notification.data.session
  const target = session ? `./#/workspace?open=${encodeURIComponent(session)}` : './'
  const url = new URL(target, self.registration.scope).href
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      if (windows.length > 0) {
        const window = await windows[0].focus()
        return window.navigate(url)
      }
      return self.clients.openWindow(url)
    })(),
  )
})
