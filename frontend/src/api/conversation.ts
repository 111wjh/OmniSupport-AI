import { API_BASE_URL } from './config'

// 一条会话摘要
export interface ConversationSummary {
  id: string
  title: string
  created_at: string
  updated_at: string
}

// 会话列表的分页响应
export interface ConversationListResponse {
  items: ConversationSummary[]
  total: number
  limit: number
  offset: number
}

// 分页查询当前客户的会话
export async function getConversations(
  token: string,
  limit: number = 20,
  offset: number = 0,
): Promise<ConversationListResponse> {
  const query = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })

  const response = await fetch(
    `${API_BASE_URL}/api/v1/conversations?${query}`,
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

    throw new Error(`获取会话列表失败，状态码：${response.status}`)
  }

  const data: ConversationListResponse | null = await response.json()

  // 检查分页响应的基本结构
  if (
    !data ||
    !Array.isArray(data.items) ||
    !Number.isInteger(data.total) ||
    data.total < 0 ||
    !Number.isInteger(data.limit) ||
    data.limit < 1 ||
    data.limit > 100 ||
    !Number.isInteger(data.offset) ||
    data.offset < 0
  ) {
    throw new Error('会话列表响应格式异常')
  }

  return data
}

// 会话中的一条消息
export interface ConversationMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

// 消息列表的分页响应
export interface ConversationMessagesResponse {
  conversation_id: string
  items: ConversationMessage[]
  total: number
  limit: number
  offset: number
}

// 分页查询指定会话的历史消息
export async function getConversationMessages(
  token: string,
  conversationId: string,
  limit: number = 20,
  offset: number = 0,
): Promise<ConversationMessagesResponse> {
  const query = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })

  const response = await fetch(
    `${API_BASE_URL}/api/v1/conversations/${encodeURIComponent(conversationId)}/messages?${query}`,
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

    if (response.status === 404) {
      throw new Error('会话不存在或无法访问')
    }

    throw new Error(`获取历史消息失败，状态码：${response.status}`)
  }

  const data: ConversationMessagesResponse | null =
    await response.json()

  if (
    !data ||
    data.conversation_id !== conversationId ||
    !Array.isArray(data.items) ||
    !Number.isInteger(data.total) ||
    data.total < 0 ||
    !Number.isInteger(data.limit) ||
    data.limit < 1 ||
    data.limit > 100 ||
    !Number.isInteger(data.offset) ||
    data.offset < 0
  ) {
    throw new Error('历史消息响应格式异常')
  }

  return data
}