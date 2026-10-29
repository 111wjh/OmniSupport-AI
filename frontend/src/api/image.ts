import { ApiError, isRecord, jsonRequest } from './http'
import type { ChatResponse } from './chat'

export function validateImage(file: File): void {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type))
    throw new ApiError('请选择 JPG、PNG 或 WEBP 图片。')
  if (file.size === 0) throw new ApiError('图片文件为空。')
  if (file.size > 5 * 1024 * 1024) throw new ApiError('图片大小不能超过 5 MB。')
}

export async function sendImageQuestion(
  token: string,
  file: File,
  question: string,
  conversationId: string | null,
): Promise<ChatResponse> {
  validateImage(file)
  const body = new FormData()
  body.append('file', file)
  body.append('question', question)
  if (conversationId) body.append('conversation_id', conversationId)
  // FormData 的 Content-Type 和 boundary 必须由浏览器生成。
  const data = await jsonRequest('/api/v1/images/upload', { token, method: 'POST', body })
  if (
    !isRecord(data) ||
    data.success !== true ||
    typeof data.answer !== 'string' ||
    typeof data.conversation_id !== 'string' ||
    !data.conversation_id ||
    (conversationId && data.conversation_id !== conversationId)
  )
    throw new ApiError('图片问答响应格式异常。')
  return { reply: data.answer, conversation_id: data.conversation_id }
}
