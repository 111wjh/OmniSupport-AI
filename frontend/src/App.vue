<script setup lang="ts">
import { onMounted } from 'vue'
import { ArrowLeft, RefreshCw } from 'lucide-vue-next'
import { useAuth } from './composables/useAuth'
import BrandMark from './components/BrandMark.vue'
import LoginForm from './components/LoginForm.vue'
import SupportWorkspace from './components/SupportWorkspace.vue'

const { token, customer, loading, error, restore, acceptLogin, logout } = useAuth()
onMounted(() => {
  void restore()
})
</script>

<template>
  <SupportWorkspace
    v-if="token && customer"
    :key="customer.id"
    :token="token"
    :customer="customer"
    @logout="logout"
  />
  <main v-else-if="token" class="session-gate">
    <BrandMark />
    <section>
      <span v-if="loading" class="spinner"></span>
      <h1>{{ loading ? '正在连接你的工作空间' : '暂时无法读取账号信息' }}</h1>
      <p>{{ error || '正在验证登录状态，请稍候…' }}</p>
      <div v-if="!loading" class="gate-actions">
        <button class="primary-button" @click="restore"><RefreshCw :size="16" />重新连接</button
        ><button class="secondary-button" @click="logout"><ArrowLeft :size="16" />返回登录</button>
      </div>
    </section>
    <span class="eyebrow">OMNISUPPORT AI / SECURE SESSION</span>
  </main>
  <LoginForm v-else :notice="error" @logged-in="acceptLogin" />
</template>
