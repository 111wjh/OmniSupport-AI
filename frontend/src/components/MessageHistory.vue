<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getConversationMessages } from '../api/conversation'
import type { ConversationMessage } from '../api/conversation'

const props = defineProps<{
  token: string
  conversationId: string
}>()

const PAGE_SIZE = 20

const messages = ref<ConversationMessage[]>([])
const total = ref<number>(0)
const offset = ref<number>(0)
const isLoading = ref<boolean>(false)
const errorMessage = ref<string>('')

async function loadPage(
  nextOffset: number = offset.value,
): Promise<void> {
  if (isLoading.value) {
    return
  }

  isLoading.value = true
  errorMessage.value = ''
  offset.value = nextOffset

  try {
    const result = await getConversationMessages(
      props.token,
      props.conversationId,
      PAGE_SIZE,
      nextOffset,
    )

    messages.value = result.items
    total.value = result.total
    offset.value = result.offset
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error ? error.message : '获取历史消息失败'
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  void loadPage()
})
</script>

<template>
  <section>
    <h2>聊天记录</h2>

    <p v-if="isLoading" role="status">
      正在加载消息…
    </p>

    <div v-else-if="errorMessage">
      <p role="alert">{{ errorMessage }}</p>
      <button type="button" @click="loadPage()">
        重试
      </button>
    </div>

    <template v-else>
      <p>共 {{ total }} 条消息，按时间从早到晚显示</p>

      <p v-if="messages.length === 0">
        这个会话还没有消息
      </p>

      <article
        v-for="message in messages"
        :key="message.id"
        class="history-message"
      >
        <h3>
          {{ message.role === 'user' ? '客户' : '智能客服' }}
        </h3>
        <p class="message-content">{{ message.content }}</p>
      </article>

      <nav v-if="total > 0" aria-label="消息分页">
        <button
          type="button"
          :disabled="offset === 0"
          @click="loadPage(Math.max(0, offset - PAGE_SIZE))"
        >
          上一页消息
        </button>

        <button
          type="button"
          :disabled="offset + PAGE_SIZE >= total"
          @click="loadPage(offset + PAGE_SIZE)"
        >
          下一页消息
        </button>
      </nav>
    </template>
  </section>
</template>

<style scoped>
.history-message {
  padding: 12px 0;
  border-bottom: 1px solid #e2e8f0;
}

.history-message h3 {
  margin: 0;
  font-size: 15px;
}

.message-content {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>