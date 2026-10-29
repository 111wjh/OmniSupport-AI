import { ApiError, isPage, isRecord, jsonRequest } from './http'

export interface ConversationSummary {
  id: string
  title: string
  created_at: string
  updated_at: string
}
export interface ConversationListResponse {
  items: ConversationSummary[]
  total: number
  limit: number
  offset: number
}
export interface ConversationMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}
export interface ConversationMessagesResponse {
  conversation_id: string
  items: ConversationMessage[]
  total: number
  limit: number
  offset: number
}

function isSummary(value: unknown): value is ConversationSummary {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.title === 'string' &&
    typeof value.created_at === 'string' &&
    typeof value.updated_at === 'string'
  )
}

function isMessage(value: unknown): value is ConversationMessage {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    (value.role === 'user' || value.role === 'assistant') &&
    typeof value.content === 'string' &&
    typeof value.created_at === 'string'
  )
}

export async function getConversations(
  token: string,
  limit = 20,
  offset = 0,
  signal?: AbortSignal,
): Promise<ConversationListResponse> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  const data = await jsonRequest(`/api/v1/conversations?${query}`, { token, signal })
  if (!isPage(data) || !data.items.every(isSummary)) throw new ApiError('会话列表格式异常。')
  return { items: data.items, total: data.total, limit: data.limit, offset: data.offset }
}

export async function getConversationMessages(
  token: string,
  conversationId: string,
  limit = 20,
  offset = 0,
  signal?: AbortSignal,
): Promise<ConversationMessagesResponse> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  const data = await jsonRequest(
    `/api/v1/conversations/${encodeURIComponent(conversationId)}/messages?${query}`,
    { token, signal },
  )
  if (!isPage(data) || data.conversation_id !== conversationId || !data.items.every(isMessage))
    throw new ApiError('历史消息格式异常。')
  return {
    conversation_id: conversationId,
    items: data.items,
    total: data.total,
    limit: data.limit,
    offset: data.offset,
  }
}
