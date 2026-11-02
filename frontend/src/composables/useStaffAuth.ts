import { onBeforeUnmount, ref } from 'vue'
import { jsonRequest, isRecord, ApiError, errorMessage, isAbort } from '../api/http'
import { record, isStaff, type Staff } from '../api/business'
const KEY = 'omnisupport.staff.token'
export function useStaffAuth() {
  const token = ref(''),
    profile = ref<Staff | null>(null),
    loading = ref(false),
    error = ref('')
  try {
    token.value = sessionStorage.getItem(KEY) || ''
  } catch {
    /* session storage is optional */
  }
  let controller: AbortController | undefined
  function persist() {
    try {
      if (token.value) sessionStorage.setItem(KEY, token.value)
      else sessionStorage.removeItem(KEY)
    } catch {
      /* keep in memory */
    }
  }
  function logout() {
    controller?.abort()
    token.value = ''
    profile.value = null
    loading.value = false
    error.value = ''
    persist()
  }
  async function restore() {
    if (!token.value) return
    controller?.abort()
    const request = new AbortController()
    controller = request
    loading.value = true
    error.value = ''
    try {
      const result = await record('/api/v1/staff/me', token.value, isStaff, {
        signal: request.signal,
      })
      if (controller === request) profile.value = result
    } catch (cause) {
      if (isAbort(cause) || controller !== request) return
      if (cause instanceof ApiError && cause.status === 401) logout()
      error.value = errorMessage(cause)
    } finally {
      if (controller === request) loading.value = false
    }
  }
  async function login(email: string, password: string) {
    if (loading.value) return
    loading.value = true
    error.value = ''
    try {
      const data = await jsonRequest('/api/v1/staff/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (
        !isRecord(data) ||
        typeof data.access_token !== 'string' ||
        !data.access_token ||
        data.token_type !== 'bearer'
      )
        throw new ApiError('登录响应格式异常。')
      token.value = data.access_token
      persist()
      await restore()
    } catch (cause) {
      error.value = errorMessage(cause)
    } finally {
      loading.value = false
    }
  }
  onBeforeUnmount(() => controller?.abort())
  return { token, profile, loading, error, login, logout, restore }
}
