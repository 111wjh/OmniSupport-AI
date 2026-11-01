// 一次发送一个 UUID；失败后相同输入复用编号。只存哈希与 UUID，不存 Token、正文或图片。
const memory = new Map<string, string>()
const prefix = 'omni.chat.request.'

async function digest(value: BufferSource): Promise<string> {
  const bytes = new Uint8Array(await crypto.subtle.digest('SHA-256', value))
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
}

export async function getChatIdentity(
  token: string,
  conversationId: string | null,
  message: string,
  file: File | null,
): Promise<{ storageKey: string; requestId: string }> {
  const imageHash = file ? await digest(await file.arrayBuffer()) : null
  const signature = JSON.stringify([token, conversationId, message, imageHash])
  const storageKey = prefix + (await digest(new TextEncoder().encode(signature)))
  let requestId = memory.get(storageKey)
  try {
    requestId ??= sessionStorage.getItem(storageKey) ?? undefined
  } catch {
    // 浏览器禁用存储时，当前页面内仍能安全复用。
  }
  requestId ??= crypto.randomUUID()
  memory.set(storageKey, requestId)
  try {
    sessionStorage.setItem(storageKey, requestId)
  } catch {
    // 使用内存副本；不阻止请求。
  }
  return { storageKey, requestId }
}

export function forgetChatIdentity(storageKey: string): void {
  memory.delete(storageKey)
  try {
    sessionStorage.removeItem(storageKey)
  } catch {
    // 内存记录已清理。
  }
}
