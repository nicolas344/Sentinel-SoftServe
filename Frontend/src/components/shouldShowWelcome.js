const STORAGE_KEY = 'sentinel_welcomed_v1'

export function shouldShowWelcome() {
  return !localStorage.getItem(STORAGE_KEY)
}
