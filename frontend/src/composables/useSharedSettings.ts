import { type WritableComputedRef, computed, ref } from 'vue'
import { type SharedSettings, api } from '../api'
import { useToast } from './useToast'

// The settings that are the same on every device (see shared_settings.py): the server's, loaded once the
// user is logged in and kept up to date by the server's events (SettingsSync). Null until loaded; what
// needs them is not shown before (App.vue).
export const sharedSettings = ref<SharedSettings | null>(null)

export async function loadSharedSettings(): Promise<void> {
  sharedSettings.value = await api.settings()
}

/** A shared setting as a ref: reading gives what the server has, writing changes it there, and every device follows. */
export function sharedSetting<K extends keyof SharedSettings>(key: K): WritableComputedRef<SharedSettings[K]> {
  const toast = useToast()
  return computed({
    get: () => (sharedSettings.value as SharedSettings)[key],
    set: (value) => {
      // Shown at once; the server answers with what it keeps.
      sharedSettings.value = { ...(sharedSettings.value as SharedSettings), [key]: value }
      api
        .changeSettings({ [key]: value })
        .then((now) => (sharedSettings.value = now))
        .catch((error) => {
          toast.error(error)
          void loadSharedSettings()
        })
    },
  })
}
