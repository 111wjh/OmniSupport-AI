import { ApiError, apiFetch, isRecord, jsonRequest } from './http'

export interface ChatRequest {
  message: string
  conversation_id: string | null
}
export interface ChatResponse {
  reply: string
  conversation_id: string
}

export async function sendChatMessage(token: string, request: ChatRequest): Promise<ChatResponse> {
  const data = await jsonRequest('/api/v1/chat', {
    token,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (
    !isRecord(data) ||
    typeof data.reply !== 'string' ||
    typeof data.conversation_id !== 'string' ||
    !data.conversation_id ||
    (request.conversation_id && data.conversation_id !== request.conversation_id)
  )
    throw new ApiError('聊天响应格式异常。')
  return { reply: data.reply, conversation_id: data.conversation_id }
}

// 只有收到 done，才表示后端生成与消息保存都完成；断流不能按成功处理。
export async function streamChatMessage(
  token: string,
  request: ChatRequest,
  onToken: (text: string) => void,
): Promise<ChatResponse> {
  const response = await apiFetch('/api/v1/chat/stream', {
    token,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream'))
    throw new ApiError('服务没有返回可读取的消息流。')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let reply = ''
  let conversationId = ''
  const handleEvent = (frame: string) => {
    let event = 'message'
    const lines: string[] = []
    for (const line of frame.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      if (line.startsWith('data:')) lines.push(line.slice(5).trimStart())
    }
    if (!lines.length) return
    let data: unknown
    try {
      data = JSON.parse(lines.join('\n'))
    } catch {
      throw new ApiError('收到无法解析的消息片段。')
    }
    if (!isRecord(data)) throw new ApiError('消息流格式异常。')
    if (event === 'token' && typeof data.content === 'string') {
      reply += data.content
      onToken(data.content)
    } else if (event === 'error') {
      throw new ApiError(typeof data.detail === 'string' ? data.detail : '客服回复未能完成。')
    } else if (event === 'done') {
      if (
        typeof data.conversation_id !== 'string' ||
        !data.conversation_id ||
        (request.conversation_id && data.conversation_id !== request.conversation_id)
      )
        throw new ApiError('消息流会话编号异常。')
      conversationId = data.conversation_id
    }
  }
  try {
    while (!conversationId) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      // 保留跨网络分片的半个 CRLF，不提前替换它。
      buffer = buffer.replace(/\r\n/g, '\n')
      let boundary: number
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        handleEvent(frame)
        if (conversationId) break
      }
      if (done) break
    }
    if (!conversationId)
      throw new ApiError('连接提前结束，回复是否保存尚未确认。请先刷新记录再决定是否重发。')
    return { reply, conversation_id: conversationId }
  } finally {
    try {
      await reader.cancel()
    } catch {
      /* 连接可能已关闭。 */
    }
    reader.releaseLock()
  }
}
