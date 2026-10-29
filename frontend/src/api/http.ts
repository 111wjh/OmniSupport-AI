import { API_BASE_URL } from './config'

export class ApiError extends Error {
  readonly status: number
  constructor(message: string, status = 0) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type ApiOptions = RequestInit & { token?: string }

// 请求只发送一次；业务写入失败时不能自动重试。
export async function apiFetch(path: string, options: ApiOptions = {}): Promise<Response> {
  const { token, ...init } = options
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('无法连接服务，请确认后端已启动并检查网络连接。')
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    const detail = isRecord(body) && typeof body.detail === 'string' ? body.detail : ''
    let message = detail || `服务请求失败（${response.status}）`
    if (response.status === 401) message = '登录已失效，请重新登录。'
    if (response.status === 422 && !detail) message = '提交内容格式不正确，请检查后重试。'
    throw new ApiError(message, response.status)
  }
  return response
}

export async function jsonRequest(path: string, options: ApiOptions = {}): Promise<unknown> {
  const response = await apiFetch(path, options)
  try {
    return await response.json()
  } catch {
    throw new ApiError('服务返回了无法读取的数据。')
  }
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

type PageEnvelope = Record<string, unknown> & {
  items: unknown[]
  total: number
  limit: number
  offset: number
}

export function isPage(value: unknown): value is PageEnvelope {
  return (
    isRecord(value) &&
    Array.isArray(value.items) &&
    typeof value.total === 'number' &&
    Number.isInteger(value.total) &&
    value.total >= 0 &&
    typeof value.limit === 'number' &&
    Number.isInteger(value.limit) &&
    value.limit > 0 &&
    value.limit <= 100 &&
    typeof value.offset === 'number' &&
    Number.isInteger(value.offset) &&
    value.offset >= 0
  )
}

export function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '操作未完成，请稍后重试。'
}
