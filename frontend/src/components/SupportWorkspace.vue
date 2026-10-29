<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  ArrowUpRight,
  BookOpenText,
  Check,
  ChevronRight,
  CircleHelp,
  Copy,
  Download,
  Image,
  LogOut,
  Menu,
  MessageSquare,
  PanelRight,
  Plus,
  ScanLine,
  ShieldCheck,
  Sparkles,
  Workflow,
  X,
  Zap,
} from 'lucide-vue-next'
import type { CustomerProfile } from '../api/customer'
import { isRecord, jsonRequest } from '../api/http'
import { useChat } from '../composables/useChat'
import { conversationTitle, splitImageMessage } from '../utils/format'
import BrandMark from './BrandMark.vue'
import ConversationList from './ConversationList.vue'
import MessageHistory from './MessageHistory.vue'
import MessageComposer from './MessageComposer.vue'

const props = defineProps<{ token: string; customer: CustomerProfile }>()
const emit = defineEmits<{ logout: [] }>()
const {
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
} = useChat(computed(() => props.token))
const composer = ref<InstanceType<typeof MessageComposer> | null>(null)
const sidebarOpen = ref(false)
const infoOpen = ref(window.innerWidth >= 1280)
const narrowScreen = ref(window.innerWidth < 1280)
const mobileScreen = ref(window.innerWidth <= 900)
const service = ref<'checking' | 'online' | 'offline'>('checking')
const copiedId = ref(false)
const toast = ref('')
let toastTimer: ReturnType<typeof setTimeout> | undefined
let healthController: AbortController | undefined
const title = computed(() => {
  if (!activeId.value) return '新对话'
  const item = activeConversation.value
  if (item?.title && item.title !== '新会话') return item.title
  return (
    previews.value[activeId.value] ||
    (item ? conversationTitle(item.title, item.updated_at) : '历史会话')
  )
})
const serviceLabel = computed(() =>
  service.value === 'online' ? '服务可用' : service.value === 'offline' ? '连接中断' : '检查连接中',
)
const lastAttachment = computed(
  () => [...messages.value].reverse().find((message) => message.attachment)?.attachment,
)

function notify(text: string) {
  toast.value = text
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toast.value = ''
    copiedId.value = false
  }, 2400)
}
async function checkService() {
  healthController?.abort()
  const request = new AbortController()
  healthController = request
  const timer = setTimeout(() => request.abort(), 5000)
  service.value = 'checking'
  try {
    const data = await jsonRequest('/health', { signal: request.signal })
    if (healthController === request)
      service.value = isRecord(data) && data.status === 'ok' ? 'online' : 'offline'
  } catch {
    if (healthController === request) service.value = 'offline'
  } finally {
    clearTimeout(timer)
  }
}
function select(id: string) {
  selectConversation(id)
  if (!busy.value) sidebarOpen.value = false
}
function createNew() {
  newConversation()
  if (!busy.value) sidebarOpen.value = false
}
function suggest(kind: 'policy' | 'orders' | 'image') {
  if (kind === 'image') composer.value?.openImagePicker()
  else
    composer.value?.setDraft(
      kind === 'policy'
        ? '请介绍退换货政策，以及申请售后需要准备哪些信息。'
        : '请帮我查询我的订单，列出订单号和当前状态。',
    )
}
async function copyId() {
  if (!activeId.value) return
  try {
    await navigator.clipboard.writeText(activeId.value)
    copiedId.value = true
    notify('会话编号已复制')
  } catch {
    notify('复制失败，请手动选择会话编号')
  }
}
function exportMessages() {
  if (!messages.value.length || busy.value) return
  const text = [
    `OmniSupport AI · ${title.value}`,
    `会话编号：${activeId.value || '尚未创建'}`,
    '',
    ...messages.value.flatMap((message) => [
      `${message.role === 'user' ? '客户' : '智能客服'}${message.state === 'unconfirmed' || message.state === 'failed' ? '（完成状态未确认）' : ''} · ${message.created_at}`,
      message.role === 'user' ? splitImageMessage(message.content).question : message.content,
      ...(message.error ? [message.error] : []),
      '',
    ]),
  ].join('\n')
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `omnisupport-${activeId.value || 'conversation'}.txt`
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  notify('已导出当前加载的聊天记录')
}
function onEscape(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    sidebarOpen.value = false
    if (window.innerWidth < 1280) infoOpen.value = false
  }
}
function onResize() {
  narrowScreen.value = window.innerWidth < 1280
  mobileScreen.value = window.innerWidth <= 900
  if (!mobileScreen.value) sidebarOpen.value = false
}
onMounted(() => {
  void checkService()
  window.addEventListener('keydown', onEscape)
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  healthController?.abort()
  clearTimeout(toastTimer)
  window.removeEventListener('keydown', onEscape)
  window.removeEventListener('resize', onResize)
})
</script>

<template>
  <div class="workspace" :class="{ 'info-hidden': !infoOpen }">
    <button
      v-if="sidebarOpen"
      class="sidebar-backdrop"
      aria-label="关闭会话菜单"
      @click="sidebarOpen = false"
    ></button>
    <aside
      class="sidebar"
      :class="{ open: sidebarOpen }"
      :inert="(mobileScreen && !sidebarOpen) || (narrowScreen && infoOpen)"
      aria-label="会话导航"
    >
      <div class="sidebar-brand">
        <BrandMark /><button
          class="icon-button mobile-only"
          aria-label="关闭会话菜单"
          @click="sidebarOpen = false"
        >
          <X :size="18" />
        </button>
      </div>
      <button class="new-conversation-button" :disabled="busy" @click="createNew">
        <Plus :size="18" /><span>开启新对话</span><span class="new-button-corner">↗</span>
      </button>
      <ConversationList
        :items="conversations"
        :total="conversationTotal"
        :loading="listLoading"
        :error="listError"
        :has-more="listHasMore"
        :active-id="activeId"
        :disabled="busy"
        :previews="previews"
        @select="select"
        @more="refreshConversations(true)"
        @refresh="refreshConversations()"
      />
      <div class="sidebar-bottom">
        <div class="sidebar-edition">
          <Zap :size="16" /><span>多模态服务引擎<small>连接知识与业务</small></span
          ><span class="edition-label">AI</span>
        </div>
        <div class="profile-row">
          <span class="profile-avatar">{{ customer.display_name.slice(0, 1).toUpperCase() }}</span
          ><span class="profile-info"
            ><strong>{{ customer.display_name }}</strong
            ><span>{{ customer.email }}</span></span
          ><button
            class="icon-button"
            :disabled="busy"
            aria-label="退出登录"
            title="退出登录"
            @click="emit('logout')"
          >
            <LogOut :size="17" />
          </button>
        </div>
      </div>
    </aside>
    <main class="chat-panel" :inert="(mobileScreen && sidebarOpen) || (narrowScreen && infoOpen)">
      <header class="workspace-header">
        <div class="workspace-heading">
          <button
            class="icon-button mobile-only"
            aria-label="打开会话菜单"
            @click="sidebarOpen = true"
          >
            <Menu :size="20" /></button
          ><span class="breadcrumb">服务工作台</span
          ><ChevronRight :size="13" class="muted breadcrumb-chevron" /><strong>智能会话</strong
          ><span class="workspace-version">MULTIMODAL</span>
        </div>
        <div class="workspace-header-actions">
          <button
            class="connection-status"
            :class="service"
            :disabled="service === 'checking'"
            :title="service === 'offline' ? '点击重新检查连接' : '检查服务连接'"
            @click="checkService"
          >
            <span class="status-dot"></span><span>{{ serviceLabel }}</span></button
          ><span class="header-action-divider"></span
          ><button
            class="icon-button"
            title="导出已加载消息"
            aria-label="导出已加载消息"
            :disabled="!messages.length || busy"
            @click="exportMessages"
          >
            <Download :size="17" /></button
          ><button
            class="icon-button info-toggle"
            :class="{ selected: infoOpen }"
            title="会话信息"
            aria-label="显示或隐藏会话信息"
            :aria-expanded="infoOpen"
            @click="infoOpen = !infoOpen"
          >
            <PanelRight :size="18" />
          </button>
        </div>
      </header>
      <div class="conversation-heading">
        <div>
          <span class="conversation-heading-marker"></span>
          <h2>{{ title }}</h2>
          <span v-if="activeId" class="conversation-kind">历史已同步</span
          ><span v-else class="conversation-kind">全新开始</span>
        </div>
        <span class="agent-indicator" :class="{ working: busy }"
          ><Sparkles :size="13" />{{ busy ? activity : 'Omni Agent' }}</span
        >
      </div>
      <div v-if="service === 'offline'" class="connection-banner" role="status">
        暂时无法连接后端。请确认服务已启动，然后<button class="text-button" @click="checkService">
          重新检查
        </button>
      </div>
      <MessageHistory
        :key="activeId || 'new'"
        :messages="messages"
        :loading="historyLoading"
        :error="historyError"
        :total="messageTotal"
        :has-older="historyOffset > 0"
        :busy="busy"
        :is-new="!activeId"
        :customer-name="customer.display_name"
        @older="loadHistory(true)"
        @retry="loadHistory()"
        @suggest="suggest"
      />
      <MessageComposer
        ref="composer"
        :busy="busy"
        :disabled="historyLoading || !!historyError"
        :activity="activity"
        :reset-key="resetComposer"
        @send="send"
      />
      <div v-if="sendError" class="send-recovery">
        <CircleHelp :size="13" /><span>未自动重发本次消息。</span
        ><button
          v-if="activeId"
          class="text-button"
          :disabled="busy || historyLoading"
          @click="loadHistory()"
        >
          刷新记录核对</button
        ><button
          v-else
          class="text-button"
          :disabled="listLoading || busy"
          @click="refreshConversations()"
        >
          刷新会话列表核对
        </button>
      </div>
    </main>
    <button
      v-if="infoOpen"
      class="info-backdrop"
      aria-label="关闭会话信息"
      @click="infoOpen = false"
    ></button>
    <aside v-if="infoOpen" class="context-panel" aria-label="会话信息">
      <div class="context-header">
        <span>会话空间</span><span class="context-header-icon"><Workflow :size="17" /></span
        ><button
          class="icon-button context-close"
          aria-label="关闭会话信息"
          @click="infoOpen = false"
        >
          <X :size="17" />
        </button>
      </div>
      <div class="context-scroll">
        <section class="agent-card">
          <div class="agent-orb"><BrandMark compact /></div>
          <span class="eyebrow">OMNI INTELLIGENCE</span>
          <h3>你的智能服务伙伴</h3>
          <p>理解文字与图像<br />连接知识与业务</p>
          <div class="agent-card-status">
            <span class="status-dot"></span>{{ busy ? activity : '等待你的提问' }}
          </div>
        </section>
        <section class="context-section">
          <div class="context-section-title"><span>会话概览</span><MessageSquare :size="13" /></div>
          <dl class="session-details">
            <div>
              <dt>当前状态</dt>
              <dd>
                <span class="small-status-dot"></span
                >{{ busy ? '正在处理' : activeId ? '会话已载入' : '新对话' }}
              </dd>
            </div>
            <div>
              <dt>已保存消息</dt>
              <dd class="mono">{{ messageTotal }}<span class="muted"> 条</span></dd>
            </div>
            <div>
              <dt>身份认证</dt>
              <dd><ShieldCheck :size="12" />已验证</dd>
            </div>
          </dl>
          <div v-if="activeId" class="session-id">
            <span>会话编号</span>
            <div>
              <code>{{ activeId }}</code
              ><button class="icon-button" aria-label="复制会话编号" @click="copyId">
                <Check v-if="copiedId" :size="13" /><Copy v-else :size="13" />
              </button>
            </div>
          </div>
        </section>
        <section class="context-section">
          <div class="context-section-title"><span>能力工具箱</span><Sparkles :size="13" /></div>
          <div class="capability-row">
            <span><BookOpenText :size="17" /></span>
            <div>
              <strong>知识问答</strong>
              <p>检索政策，解答售后问题</p>
            </div>
            <ArrowUpRight :size="13" />
          </div>
          <div class="capability-row">
            <span><ScanLine :size="17" /></span>
            <div>
              <strong>视觉理解</strong>
              <p>识别商品与可见外观信息</p>
            </div>
            <ArrowUpRight :size="13" />
          </div>
          <div class="capability-row">
            <span><Workflow :size="17" /></span>
            <div>
              <strong>业务协同</strong>
              <p>查询订单、申请与跟踪退款</p>
            </div>
            <ArrowUpRight :size="13" />
          </div>
        </section>
        <section v-if="lastAttachment" class="context-section">
          <div class="context-section-title"><span>本次上传</span><Image :size="13" /></div>
          <div class="context-attachment">
            <img :src="lastAttachment.url" :alt="lastAttachment.name" /><span>{{
              lastAttachment.name
            }}</span>
          </div>
        </section>
        <div class="context-tip">
          <CircleHelp :size="15" />
          <p>退款申请需人工审核，审核通过后才能执行模拟退款。</p>
        </div>
      </div>
      <div class="context-footer">
        <span class="tiny-cross">+</span> HUMAN-CENTERED. AI-POWERED.
      </div>
    </aside>
    <Transition name="toast"
      ><div v-if="toast" class="toast-message" role="status">
        <Check :size="15" />{{ toast }}
      </div></Transition
    >
  </div>
</template>
