import { onBeforeUnmount, ref } from 'vue'
import { getCurrentCustomer } from '../api/customer'
import type { CustomerProfile } from '../api/customer'
import { ApiError, errorMessage, isAbort } from '../api/http'

const STORAGE_KEY = 'omnisupport.customer.token'
function storedToken(): string {
  try {
    return sessionStorage.getItem(STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

// 只有凭证存入当前标签页的会话存储；密码始终不保存。
export function useAuth() {
  const token = ref(storedToken())
  const customer = ref<CustomerProfile | null>(null)
  const loading = ref(false)
  const error = ref('')
  let controller: AbortController | undefined

  function persist(value: string) {
    try {
      if (value) sessionStorage.setItem(STORAGE_KEY, value)
      else sessionStorage.removeItem(STORAGE_KEY)
    } catch {
      /* 存储不可用时仍可以在当前页面使用。 */
    }
  }

  function logout() {
    controller?.abort()
    token.value = ''
    customer.value = null
    loading.value = false
    error.value = ''
    persist('')
  }

  async function restore() {
    if (!token.value) return
    controller?.abort()
    const request = new AbortController()
    controller = request
    const currentToken = token.value
    loading.value = true
    error.value = ''
    try {
      const profile = await getCurrentCustomer(currentToken, request.signal)
      if (controller === request && token.value === currentToken) customer.value = profile
    } catch (cause) {
      if (isAbort(cause) || controller !== request) return
      if (cause instanceof ApiError && cause.status === 401) {
        logout()
        error.value = '登录已过期，请重新登录。'
      } else error.value = errorMessage(cause)
    } finally {
      if (controller === request) loading.value = false
    }
  }

  async function acceptLogin(value: string) {
    customer.value = null
    token.value = value
    persist(value)
    await restore()
  }

  onBeforeUnmount(() => controller?.abort())
  return { token, customer, loading, error, restore, acceptLogin, logout }
}
