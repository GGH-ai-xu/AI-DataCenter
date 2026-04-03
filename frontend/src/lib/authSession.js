export const AUTH_SESSION_STORAGE_KEY = 'gpu_gov_session_token'


function resolveStorage(storage) {
  if (storage) return storage
  if (typeof window === 'undefined') return null
  return window.localStorage || null
}


export function readSessionToken(storage) {
  const target = resolveStorage(storage)
  if (!target?.getItem) return ''
  return String(target.getItem(AUTH_SESSION_STORAGE_KEY) || '').trim()
}


export function writeSessionToken(token, storage) {
  const target = resolveStorage(storage)
  if (!target?.setItem || !target?.removeItem) return
  const normalized = String(token || '').trim()
  if (!normalized) {
    target.removeItem(AUTH_SESSION_STORAGE_KEY)
    return
  }
  target.setItem(AUTH_SESSION_STORAGE_KEY, normalized)
}


export function clearSessionToken(storage) {
  const target = resolveStorage(storage)
  target?.removeItem?.(AUTH_SESSION_STORAGE_KEY)
}
