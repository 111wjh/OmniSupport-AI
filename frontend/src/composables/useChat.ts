import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import type { Ref } from 'vue'
import { getConversations, getConversationMessages } from '../api/conversation'
import type { ConversationMessage, ConversationSummary } from '../api/conversation'
import { sendChatMessage, streamChatMessage } from '../api/chat'
import { sendImageQuestion } from '../api/image'
import { errorMessage, isAbort } from '../api/http'
import { splitImageMessage } from '../utils/format'

export interface DisplayMessage extends ConversationMessage {
  state?: 'pending' | 'complete' | 'unconfirmed' | 'failed'
  attachment?: { name: string; url: string }
  error?: string
}
export interface SendInput {
  text: string
  file: File | null
  stream: boolean
}

const PAGE_SIZE = 20

// 读请求可以取消；写请求只提交一次，只有成功响应才标记为已保存。
export function useChat(token: Readonly<Ref<string>>) {
  const conversations = ref<ConversationSummary[]>([])
  const conversationTotal = ref(0)
  const listHasMore = ref(false)
  const listLoading = ref(false)
  const listError = ref('')
  const previews = ref<Record<string, string>>({})
  const activeId = ref<string | null>(null)
  const messages = ref<DisplayMessage[]>([])
  const messageTotal = ref(0)
  const historyOffset = ref(0)
  const historyLoading = ref(false)
  const historyError = ref('')
  const busy = ref(false)
  const activity = ref('')
  const sendError = ref('')
  const resetComposer = ref(0)
  let listOffset = 0
  let generation = 0
  let listRequest: AbortController | undefined
  let historyRequest: AbortController | undefined
  const attachmentUrls = new Set<string>()

  const activeConversation = computed(() =>
    conversations.value.find((item) => item.id === activeId.value),
  )

  function clearAttachments() {
    attachmentUrls.forEach((url) => URL.revokeObjectURL(url))
    attachmentUrls.clear()
  }

  async function refreshConversations(append = false) {
    if (append && listLoading.value) return
    listRequest?.abort()
    const request = new AbortController()
    listRequest = request
    listLoading.value = true
    listError.value = ''
    try {
      const page = await getConversations(
        token.value,
        PAGE_SIZE,
        append ? listOffset : 0,
        request.signal,
      )
      if (listRequest !== request) return
      conversations.value = append
        ? Array.from(
            new Map(
              [...conversations.value, ...page.items].map((item) => [item.id, item]),
            ).values(),
          )
        : page.items
      listOffset = page.offset + page.items.length
      conversationTotal.value = page.total
      listHasMore.value = page.items.length > 0 && listOffset < page.total
    } catch (cause) {
      if (!isAbort(cause) && listRequest === request) listError.value = errorMessage(cause)
    } finally {
      if (listRequest === request) listLoading.value = false
    }
  }

  async function loadHistory(older = false) {
    if (
      !activeId.value ||
      busy.value ||
      (older && (historyLoading.value || historyOffset.value === 0))
    )
      return
    historyRequest?.abort()
    const request = new AbortController()
    historyRequest = request
    const id = activeId.value
    historyLoading.value = true
    historyError.value = ''
    try {
      let page
      if (older) {
        const offset = Math.max(0, historyOffset.value - PAGE_SIZE)
        page = await getConversationMessages(
          token.value,
          id,
          historyOffset.value - offset,
          offset,
          request.signal,
        )
      } else {
        // 后端按时间升序分页，先取得总数，再定位最近 20 条。
        page = await getConversationMessages(token.value, id, PAGE_SIZE, 0, request.signal)
        if (page.total > PAGE_SIZE)
          page = await getConversationMessages(
            token.value,
            id,
            PAGE_SIZE,
            page.total - PAGE_SIZE,
            request.signal,
          )
      }
      if (historyRequest !== request || activeId.value !== id) return
      messages.value = older ? [...page.items, ...messages.value] : page.items
      messageTotal.value = page.total
      historyOffset.value = page.offset
      const firstUser = page.items.find((item) => item.role === 'user')
      if (firstUser && !previews.value[id])
        previews.value[id] = splitImageMessage(firstUser.content).question.slice(0, 50)
    } catch (cause) {
      if (!isAbort(cause) && historyRequest === request) historyError.value = errorMessage(cause)
    } finally {
      if (historyRequest === request) historyLoading.value = false
    }
  }

  function selectConversation(id: string) {
    if (busy.value || activeId.value === id) return
    historyRequest?.abort()
    clearAttachments()
    activeId.value = id
    messages.value = []
    messageTotal.value = 0
    historyOffset.value = 0
    historyError.value = ''
    sendError.value = ''
    resetComposer.value++
    void loadHistory()
  }

  function newConversation() {
    if (busy.value) return
    historyRequest?.abort()
    clearAttachments()
    activeId.value = null
    messages.value = []
    messageTotal.value = 0
    historyOffset.value = 0
    historyLoading.value = false
    historyError.value = ''
    sendError.value = ''
    resetComposer.value++
  }

  async function send(input: SendInput): Promise<boolean> {
    if (busy.value || historyLoading.value || historyError.value) return false
    const text = input.text.trim()
    const limit = input.file ? 1000 : 2000
    if (!text || text.length > limit) {
      sendError.value = `请输入 1–${limit} 个字符的问题。`
      return false
    }
    const session = generation
    const originalId = activeId.value
    const now = new Date().toISOString()
    const user = reactive<DisplayMessage>({
      id: `local-${crypto.randomUUID()}`,
      role: 'user',
      content: text,
      created_at: now,
      state: 'pending',
    })
    if (input.file) {
      const url = URL.createObjectURL(input.file)
      attachmentUrls.add(url)
      user.attachment = { name: input.file.name, url }
    }
    const assistant = reactive<DisplayMessage>({
      id: `local-${crypto.randomUUID()}`,
      role: 'assistant',
      content: '',
      created_at: now,
      state: 'pending',
    })
    messages.value.push(user, assistant)
    busy.value = true
    sendError.value = ''
    activity.value = input.file ? '正在分析图片' : '正在生成回复'
    try {
      const request = { message: text, conversation_id: originalId }
      const result = input.file
        ? await sendImageQuestion(token.value, input.file, text, originalId)
        : input.stream
          ? await streamChatMessage(token.value, request, (chunk) => {
              if (generation === session) assistant.content += chunk
            })
          : await sendChatMessage(token.value, request)
      if (generation !== session) return false
      assistant.content = result.reply
      assistant.state = 'complete'
      user.state = 'complete'
      activeId.value = result.conversation_id
      previews.value[result.conversation_id] = text.slice(0, 50)
      messageTotal.value += 2
      resetComposer.value++
      void refreshConversations()
      return true
    } catch (cause) {
      if (generation !== session) return false
      user.state = 'unconfirmed'
      assistant.state = 'failed'
      assistant.error = errorMessage(cause)
      sendError.value = errorMessage(cause)
      return false
    } finally {
      if (generation === session) {
        busy.value = false
        activity.value = ''
      }
    }
  }

  watch(
    token,
    () => {
      generation++
      listRequest?.abort()
      historyRequest?.abort()
      busy.value = false
      conversations.value = []
      previews.value = {}
      listOffset = 0
      newConversation()
      if (token.value) void refreshConversations()
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    generation++
    listRequest?.abort()
    historyRequest?.abort()
    clearAttachments()
  })

  return {
    conversations,
    conversationTotal,
    listHasMore,
    listLoading,
    listError,
    previews,
    activeId,
    activeConversation,
    messages,
    messageTotal,
    historyOffset,
    historyLoading,
    historyError,
    busy,
    activity,
    sendError,
    resetComposer,
    refreshConversations,
    loadHistory,
    selectConversation,
    newConversation,
    send,
  }
}
