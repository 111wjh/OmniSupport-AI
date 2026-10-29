<script setup lang="ts">
import { ref } from 'vue'
import { login } from '../api/auth'

const email = ref<string>('')
const password = ref<string>('')
const message = ref<string>('')

const isSubmitting = ref<boolean>(false)
// 登录成功时，通知使用本组件的父组件
const emit = defineEmits<{
  'logged-in': [token: string]
}>()

async function handleLogin(): Promise<void> {
  if (isSubmitting.value) {
    return
  }

  isSubmitting.value = true
  message.value = ''

  try {
    const result = await login({
      email: email.value.trim(),
      password: password.value,
    })

    password.value = ''
    emit('logged-in', result.access_token)
  } catch (error: unknown) {
    message.value =
      error instanceof Error ? error.message : '登录失败，请稍后重试'
  } finally {
    isSubmitting.value = false
  }
}
</script>
<template>
  <main class="login-page">
    <section class="login-card">
      <h1>OmniSupport AI</h1>
      <p>登录后开始与智能客服对话</p>

      <form @submit.prevent="handleLogin">
        <label for="email">邮箱</label>
        <input
          id="email"
          v-model="email"
          type="email"
          autocomplete="username"
          placeholder="请输入客户邮箱"
          required
        />

        <label for="password">密码</label>
        <input
          id="password"
          v-model="password"
          type="password"
          autocomplete="current-password"
          placeholder="请输入密码"
          required
        />

        <button type="submit" :disabled="isSubmitting">
          {{ isSubmitting ? '登录中…' : '登录' }}
        </button>
      </form>

      <p role="status">{{ message }}</p>
    </section>
  </main>
</template>