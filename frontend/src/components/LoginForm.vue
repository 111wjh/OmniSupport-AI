<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  ArrowRight,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  ScanLine,
  Sparkles,
  UserRound,
  ShieldCheck,
  Workflow,
} from 'lucide-vue-next'
import { login, registerCustomer } from '../api/auth'
import { errorMessage } from '../api/http'
import BrandMark from './BrandMark.vue'

defineProps<{ notice?: string }>()
const emit = defineEmits<{ 'logged-in': [token: string] }>()
const mode = ref<'login' | 'register'>('login')
const email = ref('')
const password = ref('')
const displayName = ref('')
const visiblePassword = ref(false)
const submitting = ref(false)
const error = ref('')
const information = ref('')
const isRegister = computed(() => mode.value === 'register')

function changeMode(value: 'login' | 'register') {
  if (submitting.value) return
  mode.value = value
  error.value = ''
  information.value = ''
  password.value = ''
}

async function handleSubmit() {
  if (submitting.value) return
  error.value = ''
  information.value = ''
  submitting.value = true
  try {
    const credentials = { email: email.value.trim(), password: password.value }
    if (isRegister.value) {
      await registerCustomer({ ...credentials, display_name: displayName.value.trim() })
      mode.value = 'login'
      password.value = ''
      information.value = '账号已创建，请输入密码登录。'
    } else {
      const result = await login(credentials)
      password.value = ''
      emit('logged-in', result.access_token)
    }
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <header class="auth-header">
      <BrandMark /><span class="header-caption"
        ><span class="tiny-cross">+</span> 多模态智能客服平台</span
      >
    </header>
    <main class="auth-main">
      <section class="auth-story">
        <div class="eyebrow"><span class="status-dot"></span> INTELLIGENCE, WITH UNDERSTANDING</div>
        <h1>理解每一个问题。<br /><span>连接每一种可能。</span></h1>
        <p class="auth-description">
          从一句提问，到一张图片。让知识与业务协同，<br
            class="desktop-only"
          />为每一次服务，找到更清晰的答案。
        </p>
        <div class="auth-orbit" aria-hidden="true">
          <div class="orbit-ring orbit-ring-one"></div>
          <div class="orbit-ring orbit-ring-two"></div>
          <div class="orbit-ring orbit-ring-three"></div>
          <div class="orbit-axis axis-x"></div>
          <div class="orbit-axis axis-y"></div>
          <div class="orbit-core"><BrandMark compact /></div>
          <span class="orbit-node node-one"><ScanLine :size="19" /></span
          ><span class="orbit-node node-two"><Workflow :size="19" /></span
          ><span class="orbit-node node-three"><Sparkles :size="19" /></span>
          <span class="orbit-label">MULTIMODAL NEURAL INTERFACE</span>
        </div>
        <div class="auth-capabilities">
          <span><Sparkles :size="15" /> 智能对话</span><span><ScanLine :size="15" /> 图像理解</span
          ><span><Workflow :size="15" /> 业务协同</span>
        </div>
      </section>
      <section class="auth-card" aria-labelledby="auth-title">
        <div class="auth-card-marker">YOUR WORKSPACE STARTS HERE <span>↗</span></div>
        <h2 id="auth-title">
          {{ isRegister ? '创建你的账号' : '欢迎回来' }}<span class="accent">.</span>
        </h2>
        <p class="muted auth-subtitle">
          {{ isRegister ? '开启你的智能服务体验' : '登录 OmniSupport，开启智能服务体验' }}
        </p>
        <div class="auth-tabs" aria-label="账号操作">
          <button
            type="button"
            :class="{ active: !isRegister }"
            :disabled="submitting"
            @click="changeMode('login')"
          >
            账号登录</button
          ><button
            type="button"
            :class="{ active: isRegister }"
            :disabled="submitting"
            @click="changeMode('register')"
          >
            注册账号
          </button>
        </div>
        <form class="auth-form" @submit.prevent="handleSubmit">
          <label v-if="isRegister" class="field-label" for="display-name"
            >你的称呼
            <div class="field-control">
              <UserRound :size="17" /><input
                id="display-name"
                v-model="displayName"
                autocomplete="nickname"
                maxlength="100"
                placeholder="我们该如何称呼你"
                required
                :disabled="submitting"
              /></div
          ></label>
          <label class="field-label" for="email"
            >邮箱地址
            <div class="field-control">
              <Mail :size="17" /><input
                id="email"
                v-model="email"
                type="email"
                autocomplete="username"
                placeholder="name@example.com"
                required
                :disabled="submitting"
              /></div
          ></label>
          <label class="field-label" for="password"
            >密码
            <div class="field-control">
              <LockKeyhole :size="17" /><input
                id="password"
                v-model="password"
                :type="visiblePassword ? 'text' : 'password'"
                :autocomplete="isRegister ? 'new-password' : 'current-password'"
                :minlength="isRegister ? 8 : 1"
                maxlength="128"
                :placeholder="isRegister ? '至少 8 个字符' : '请输入你的密码'"
                required
                :disabled="submitting"
              /><button
                type="button"
                class="icon-button"
                :aria-label="visiblePassword ? '隐藏密码' : '显示密码'"
                @click="visiblePassword = !visiblePassword"
              >
                <EyeOff v-if="visiblePassword" :size="17" /><Eye v-else :size="17" />
              </button></div
          ></label>
          <p v-if="error || notice" class="form-error" role="alert">{{ error || notice }}</p>
          <p v-if="information" class="form-success" role="status">{{ information }}</p>
          <button class="primary-button auth-submit" :disabled="submitting" type="submit">
            <span v-if="submitting" class="spinner"></span
            >{{ submitting ? '正在连接…' : isRegister ? '创建账号' : '进入工作台'
            }}<ArrowRight v-if="!submitting" :size="18" />
          </button>
        </form>
        <div class="auth-session-note">
          <ShieldCheck :size="15" /><span>登录状态保留在当前浏览器标签页</span>
        </div>
      </section>
    </main>
    <footer class="auth-footer">
      <span>© {{ new Date().getFullYear() }} OmniSupport AI</span
      ><span>BUILT FOR BETTER CONVERSATIONS <span class="accent">✦</span></span>
    </footer>
  </div>
</template>
