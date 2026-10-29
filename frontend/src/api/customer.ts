import { API_BASE_URL } from './config'

// 与后端 CustomerResponse 对应
export interface CustomerProfile {
  id: string
  email: string
  display_name: string
  is_active: boolean
}

// 使用访问凭证查询当前客户资料
export async function getCurrentCustomer(
  token: string,
): Promise<CustomerProfile> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/customers/me`,
    {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  )

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('登录凭证无效或已过期，请重新登录')
    }

    throw new Error(`获取客户信息失败，状态码：${response.status}`)
  }

  const data: CustomerProfile | null = await response.json()

  if (
    !data ||
    typeof data.id !== 'string' ||
    typeof data.email !== 'string' ||
    typeof data.display_name !== 'string' ||
    typeof data.is_active !== 'boolean'
  ) {
    throw new Error('客户信息响应格式异常')
  }

  return data
}