<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getConversations } from '../api/conversation'
import type { ConversationSummary } from '../api/conversation'

// 父组件传入登录凭证
const props = defineProps<{
  token: string
}>()
const emit = defineEmits<{
  'select-conversation': [conversationId: string]
}>()
// 每页显示 5 条，便于观察分页效果
const PAGE_SIZE = 5

const conversations = ref<ConversationSummary[]>([])
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

  // 记住目标页，失败后可以重试同一页
  offset.value = nextOffset

  try {
    const result = await getConversations(
      props.token,
      PAGE_SIZE,
      nextOffset,
    )

    conversations.value = result.items
    total.value = result.total
    offset.value = result.offset
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error ? error.message : '获取会话列表失败'
  } finally {
    isLoading.value = false
  }
}

function formatTime(value: string): string {
  return new Date(value).toLocaleString('zh-CN', {
    hour12: false,
  })
}

// 组件首次显示后，自动加载第一页
onMounted(() => {
  void loadPage()
})
</script>

<template>
  <section>
    <h2>历史会话</h2>

    <p v-if="isLoading" role="status">
      正在加载会话…
    </p>

    <div v-else-if="errorMessage">
      <p role="alert">{{ errorMessage }}</p>
      <button type="button" @click="loadPage()">
        重试
      </button>
    </div>

    <template v-else>
      <p>共 {{ total }} 条会话</p>

      <p v-if="conversations.length === 0">
        暂无会话记录
      </p>

      <ul v-else class="conversation-items">
        <li
          v-for="conversation in conversations"
          :key="conversation.id"
        >
            <button
            type="button"
            @click="emit('select-conversation', conversation.id)"
            >
            {{ conversation.title }}
            </button>
          <p>{{ formatTime(conversation.updated_at) }}</p>
        </li>
      </ul>

      <nav v-if="total > 0" aria-label="会话分页">
        <button
          type="button"
          :disabled="offset === 0"
          @click="loadPage(Math.max(0, offset - PAGE_SIZE))"
        >
          上一页
        </button>

        <button
          type="button"
          :disabled="offset + PAGE_SIZE >= total"
          @click="loadPage(offset + PAGE_SIZE)"
        >
          下一页
        </button>
      </nav>
    </template>
  </section>
</template>

<style scoped>
.conversation-items {
  padding: 0;
  list-style: none;
}

.conversation-items li {
  padding: 12px 0;
  border-bottom: 1px solid #e2e8f0;
}

.conversation-items p {
  margin: 6px 0 0;
  font-size: 14px;
}
</style>