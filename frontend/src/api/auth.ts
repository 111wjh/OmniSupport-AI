import { ApiError, isRecord, jsonRequest } from './http'

export interface LoginRequest {
  email: string
  password: string
}
export interface LoginResponse {
  access_token: string
  token_type: string
}

export async function login(credentials: LoginRequest): Promise<LoginResponse> {
  let data: unknown
  try {
    data = await jsonRequest('/api/v1/customers/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
    })
  } catch (error) {
    if (error instanceof ApiError && error.status === 401)
      throw new ApiError('邮箱或密码错误，或账号不可用。', 401)
    throw error
  }
  if (
    !isRecord(data) ||
    typeof data.access_token !== 'string' ||
    !data.access_token ||
    data.token_type !== 'bearer'
  ) {
    throw new ApiError('登录响应格式异常。')
  }
  return { access_token: data.access_token, token_type: data.token_type }
}

export async function registerCustomer(
  data: LoginRequest & { display_name: string },
): Promise<void> {
  await jsonRequest('/api/v1/customers/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}
