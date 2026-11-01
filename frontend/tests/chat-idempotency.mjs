import assert from 'node:assert/strict'
import { webcrypto } from 'node:crypto'
import { createServer } from 'vite'
import { ref, createRenderer } from 'vue'

// 使用真实 composable 和请求层，以模拟服务器验证重试协议；不访问真实后端。
globalThis.crypto ??= webcrypto
const storage = new Map()
globalThis.sessionStorage = {
  getItem: (key) => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, value),
  removeItem: (key) => storage.delete(key),
}
const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
const apps = []
const renderer = createRenderer({
  createComment: () => ({}),
  insert() {},
  remove() {},
  parentNode: () => null,
  nextSibling: () => null,
  createElement: () => ({}),
  createText: () => ({}),
  setText() {},
  setElementText() {},
  patchProp() {},
})
try {
  const { useChat } = await server.ssrLoadModule('/src/composables/useChat.ts')
  const received = []
  const committed = new Map()
  const histories = new Map()
  let failNext = false
  const json = (data) =>
    new Response(JSON.stringify(data), {
      headers: { 'Content-Type': 'application/json' },
    })
  globalThis.fetch = async (url, options = {}) => {
    const path = new URL(url).pathname
    if (options.method === 'POST') {
      const body =
        options.body instanceof FormData
          ? Object.fromEntries(options.body.entries())
          : JSON.parse(options.body)
      received.push(body)
      let result = committed.get(body.client_request_id)
      if (!result) {
        const id = body.conversation_id || crypto.randomUUID()
        result = { reply: '工单回执', conversation_id: id }
        committed.set(body.client_request_id, result)
        histories.set(id, [
          ...(histories.get(id) ?? []),
          {
            id: crypto.randomUUID(),
            role: 'user',
            created_at: new Date().toISOString(),
            content: body.message ?? body.question,
          },
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            created_at: new Date().toISOString(),
            content: result.reply,
          },
        ])
      }
      if (failNext) {
        failNext = false
        throw new TypeError('模拟服务端提交后响应丢失')
      }
      if (path.endsWith('/stream')) {
        return new Response(
          'event: token\ndata: ' +
            JSON.stringify({ content: result.reply }) +
            '\n\nevent: done\ndata: ' +
            JSON.stringify({ conversation_id: result.conversation_id }) +
            '\n\n',
          { headers: { 'Content-Type': 'text/event-stream' } },
        )
      }
      return json(
        path.endsWith('/upload')
          ? { success: true, answer: result.reply, conversation_id: result.conversation_id }
          : result,
      )
    }
    if (path.endsWith('/messages')) {
      const id = path.split('/').at(-2)
      const items = histories.get(id) ?? []
      return json({ conversation_id: id, items, total: items.length, limit: 20, offset: 0 })
    }
    return json({ items: [], total: 0, limit: 20, offset: 0 })
  }
  const settle = async (chat) => {
    for (let i = 0; i < 200; i++) {
      await new Promise((resolve) => setTimeout(resolve, 5))
      if (!chat.historyLoading.value && !chat.busy.value) return
    }
    throw new Error('页面未结束加载')
  }
  const mountChat = () => {
    let chat
    const app = renderer.createApp({
      setup() {
        chat = useChat(ref('test-customer-token'))
        return () => null
      },
    })
    app.mount({})
    apps.push(app)
    return chat
  }
  const chat = mountChat()
  await settle(chat)

  failNext = true
  assert.equal(await chat.send({ text: '创建工单', file: null, stream: true }), false)
  const firstId = received.at(-1).client_request_id
  assert.equal(await chat.send({ text: '创建工单', file: null, stream: false }), true)
  await settle(chat)
  assert.equal(received.at(-1).client_request_id, firstId)
  assert.equal(committed.size, 1)
  assert.equal(chat.messages.value.length, 2, '重试后用服务端历史替换本地失败气泡')

  await chat.send({ text: '新消息', file: null, stream: false })
  await settle(chat)
  assert.notEqual(received.at(-1).client_request_id, firstId, '新消息使用新编号')

  chat.newConversation()
  failNext = true
  const image = new File(['same-image'], 'first.png', { type: 'image/png' })
  assert.equal(await chat.send({ text: '图片建单', file: image, stream: false }), false)
  const imageId = received.at(-1).client_request_id
  const reselected = new File(['same-image'], 'renamed.png', { type: 'image/png' })
  assert.equal(await chat.send({ text: '图片建单', file: reselected, stream: false }), true)
  await settle(chat)
  assert.equal(received.at(-1).client_request_id, imageId, '相同图片字节可以重新选择文件后重试')

  chat.newConversation()
  failNext = true
  assert.equal(await chat.send({ text: '刷新前失败', file: null, stream: false }), false)
  const beforeReload = received.at(-1).client_request_id
  const reloaded = mountChat()
  await settle(reloaded)
  assert.equal(await reloaded.send({ text: '刷新前失败', file: null, stream: false }), true)
  await settle(reloaded)
  assert.equal(received.at(-1).client_request_id, beforeReload, '同标签页刷新后复用保存的编号')
  console.log('4 scenarios passed: cross-transport retry, new send, image retry, reload recovery')
} finally {
  apps.forEach((app) => app.unmount())
  await server.close()
}
