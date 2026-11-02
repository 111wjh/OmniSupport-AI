<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useAuth } from './composables/useAuth'
import { useStaffAuth } from './composables/useStaffAuth'
import BrandMark from './components/BrandMark.vue'
import LoginForm from './components/LoginForm.vue'
import SupportWorkspace from './components/SupportWorkspace.vue'
import BusinessWorkspace from './components/BusinessWorkspace.vue'
const { token, customer, loading, error, restore, acceptLogin, logout } = useAuth()
const employee = useStaffAuth()
const staffMode = ref(window.location.hash === '#staff')
const tab = ref<'chat' | 'orders' | 'refunds' | 'tickets'>('chat')
const email = ref(''),
  password = ref('')
function route() {
  staffMode.value = window.location.hash === '#staff'
}
function switchMode() {
  window.location.hash = staffMode.value ? '' : 'staff'
}
async function staffLogin() {
  await employee.login(email.value.trim(), password.value)
  password.value = ''
}
onMounted(() => {
  void restore()
  void employee.restore()
  window.addEventListener('hashchange', route)
})
onBeforeUnmount(() => window.removeEventListener('hashchange', route))
</script>
<template>
  <div v-if="staffMode" class="application-shell">
    <header class="application-nav">
      <BrandMark compact /><strong>OmniSupport <span class="nav-muted">/ 员工控制台</span></strong>
      <div class="application-tabs">
        <button @click="switchMode">客户入口</button
        ><button v-if="employee.profile.value" @click="employee.logout">退出员工账号</button>
      </div>
    </header>
    <BusinessWorkspace
      v-if="employee.token.value && employee.profile.value"
      :key="employee.profile.value.id"
      :token="employee.token.value"
      :staff="employee.profile.value"
    />
    <main v-else class="staff-entry">
      <section class="staff-login">
        <span class="eyebrow">AUTHORIZED PERSONNEL</span>
        <h1>服务，从这里接力。</h1>
        <p>登录员工工作台，处理人工工单与退款审核。</p>
        <form v-if="!employee.token.value" class="desk-form" @submit.prevent="staffLogin">
          <label
            >员工邮箱<input v-model="email" type="email" autocomplete="username" required /></label
          ><label
            >密码<input
              v-model="password"
              type="password"
              autocomplete="current-password"
              required
              maxlength="128" /></label
          ><button class="primary-button" :disabled="employee.loading.value">
            {{ employee.loading.value ? '正在验证…' : '登录工作台 →' }}
          </button>
        </form>
        <div v-else class="desk-actions">
          <button :disabled="employee.loading.value" @click="employee.restore">
            重新读取员工身份</button
          ><button @click="employee.logout">返回员工登录</button>
        </div>
        <p v-if="employee.error.value" class="desk-error" role="alert">
          {{ employee.error.value }}
        </p>
        <small>员工账号由项目命令创建，权限以服务端角色校验为准。</small>
      </section>
      <aside>
        <span class="staff-orbit">◎</span>
        <h2>Human judgment.<br />Intelligent support.</h2>
        <p>人工判断与 AI 协作，构成完整的售后服务链路。</p>
      </aside>
    </main>
  </div>
  <div v-else-if="token && customer" class="application-shell">
    <header class="application-nav">
      <BrandMark compact /><strong>OmniSupport</strong>
      <nav class="application-tabs" aria-label="客户工作区">
        <button
          v-for="item in [
            ['chat', '智能会话'],
            ['orders', '我的订单'],
            ['refunds', '退款进度'],
            ['tickets', '人工工单'],
          ] as const"
          :key="item[0]"
          :class="{ active: tab === item[0] }"
          @click="tab = item[0]"
        >
          {{ item[1] }}
        </button>
      </nav>
      <button class="nav-employee" @click="switchMode">员工入口 ↗</button
      ><button class="nav-employee" @click="logout">退出客户账号</button>
    </header>
    <div class="application-content">
      <SupportWorkspace
        v-show="tab === 'chat'"
        :key="customer.id"
        :token="token"
        :customer="customer"
        @logout="logout"
      /><BusinessWorkspace
        v-if="tab !== 'chat'"
        :key="customer.id + tab"
        :view="tab"
        :token="token"
      />
    </div>
  </div>
  <main v-else-if="token" class="session-gate">
    <BrandMark />
    <section>
      <h1>{{ loading ? '正在连接你的工作空间' : '暂时无法读取账号信息' }}</h1>
      <p>{{ error || '正在验证登录状态，请稍候…' }}</p>
      <div v-if="!loading" class="gate-actions">
        <button class="primary-button" @click="restore">重新连接</button
        ><button class="secondary-button" @click="logout">返回登录</button>
      </div>
    </section>
  </main>
  <template v-else
    ><button class="staff-entry-link" @click="switchMode">员工工作台 ↗</button
    ><LoginForm :notice="error" @logged-in="acceptLogin"
  /></template>
</template>
