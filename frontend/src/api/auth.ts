import { API_BASE_URL } from './config'

// 登录请求的数据结构
export interface LoginRequest {
  email: string
  password: string
}

// 登录成功响应的数据结构
export interface LoginResponse {
  access_token: string
  token_type: string
}

// 验证账号并取得访问凭证
export async function login(
  credentials: LoginRequest,
): Promise<LoginResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/customers/login`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(credentials),
    },
  )

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('邮箱或密码错误，或账号不可用')
    }

    if (response.status === 422) {
      throw new Error('请检查邮箱和密码格式')
    }

    throw new Error(`登录失败，状态码：${response.status}`)
  }

  const data: LoginResponse | null = await response.json()

  // TypeScript 类型只在开发时检查，实际响应仍需要校验
  if (
    !data ||
    typeof data.access_token !== 'string' ||
    !data.access_token ||
    data.token_type !== 'bearer'
  ) {
    throw new Error('登录响应格式异常')
  }

  return data
}