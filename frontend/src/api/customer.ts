import { ApiError, isRecord, jsonRequest } from './http'

export interface CustomerProfile {
  id: string
  email: string
  display_name: string
  is_active: boolean
}

export async function getCurrentCustomer(
  token: string,
  signal?: AbortSignal,
): Promise<CustomerProfile> {
  const data = await jsonRequest('/api/v1/customers/me', { token, signal })
  if (
    !isRecord(data) ||
    typeof data.id !== 'string' ||
    typeof data.email !== 'string' ||
    typeof data.display_name !== 'string' ||
    typeof data.is_active !== 'boolean'
  )
    throw new ApiError('客户资料格式异常。')
  return {
    id: data.id,
    email: data.email,
    display_name: data.display_name,
    is_active: data.is_active,
  }
}
