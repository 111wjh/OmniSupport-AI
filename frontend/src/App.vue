<script setup lang="ts">
import { ref } from 'vue'
import LoginForm from './components/LoginForm.vue'
import { getCurrentCustomer } from './api/customer'
import type { CustomerProfile } from './api/customer'
import ConversationList from './components/ConversationList.vue'
import MessageHistory from './components/MessageHistory.vue'
const accessToken = ref<string>('')
const customer = ref<CustomerProfile | null>(null)
const isLoading = ref<boolean>(false)
const errorMessage = ref<string>('')
const selectedConversationId = ref<string>('')
// 查询资料；首次登录和点击重试共用这个函数
async function loadCustomer(): Promise<void> {
  const token = accessToken.value

  if (!token || isLoading.value) {
    return
  }

  isLoading.value = true
  errorMessage.value = ''

  try {
    const result = await getCurrentCustomer(token)

    // 退出或切换账号后，不再使用旧请求的结果
    if (accessToken.value === token) {
      customer.value = result
    }
  } catch (error: unknown) {
    if (accessToken.value === token) {
      errorMessage.value =
        error instanceof Error ? error.message : '获取客户信息失败'
    }
  } finally {
    if (accessToken.value === token) {
      isLoading.value = false
    }
  }
}
function handleConversationSelected(conversationId: string): void {
  selectedConversationId.value = conversationId
}
async function handleLoggedIn(token: string): Promise<void> {
  accessToken.value = token
  customer.value = null
  selectedConversationId.value = ''
  await loadCustomer()
}

function handleLogout(): void {
  accessToken.value = ''
  customer.value = null
  errorMessage.value = ''
  isLoading.value = false
  selectedConversationId.value = ''
}
</script>

<template>
  <LoginForm
    v-if="!accessToken"
    @logged-in="handleLoggedIn"
  />

  <main v-else class="login-page">
    <section class="login-card">
      <h1>OmniSupport AI</h1>

      <p v-if="isLoading" role="status">
        正在读取客户信息…
      </p>

      <div v-else-if="errorMessage">
        <p role="alert">{{ errorMessage }}</p>
        <button type="button" @click="loadCustomer">
          重试
        </button>
      </div>

      <div v-else-if="customer">
        <p>你好，{{ customer.display_name }}！</p>
        <p>当前账号：{{ customer.email }}</p>

        <ConversationList
          :key="accessToken"
          :token="accessToken"
          @select-conversation="handleConversationSelected"
        />

        <MessageHistory
          v-if="selectedConversationId"
          :key="accessToken + ':' + selectedConversationId"
          :token="accessToken"
          :conversation-id="selectedConversationId"
        />

        <p v-else>请选择一条会话查看聊天记录。</p>
      </div>

      <button type="button" @click="handleLogout">
        退出登录
      </button>
    </section>
  </main>
</template>