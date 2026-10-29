<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import {
  ArrowDown,
  ArrowUp,
  Check,
  Copy,
  Image,
  MessageSquare,
  ScanLine,
  ShoppingBag,
  Sparkles,
  TriangleAlert,
} from 'lucide-vue-next'
import type { DisplayMessage } from '../composables/useChat'
import { formatTime, splitImageMessage } from '../utils/format'
import BrandMark from './BrandMark.vue'
import MarkdownText from './MarkdownText.vue'

const props = defineProps<{
  messages: DisplayMessage[]
  loading: boolean
  error: string
  total: number
  hasOlder: boolean
  busy: boolean
  isNew: boolean
  customerName: string
}>()
const emit = defineEmits<{ older: []; retry: []; suggest: [kind: 'policy' | 'orders' | 'image'] }>()
const viewport = ref<HTMLDivElement | null>(null)
const followBottom = ref(true)
const copied = ref('')
let copyTimer: ReturnType<typeof setTimeout> | undefined
let prependAnchor: { height: number; top: number } | null = null

function onScroll() {
  const element = viewport.value
  if (element)
    followBottom.value = element.scrollHeight - element.scrollTop - element.clientHeight < 130
}
function bottom() {
  const element = viewport.value
  if (element) element.scrollTop = element.scrollHeight
  followBottom.value = true
}
function older() {
  const element = viewport.value
  if (element) prependAnchor = { height: element.scrollHeight, top: element.scrollTop }
  emit('older')
}
async function copyMessage(message: DisplayMessage) {
  try {
    await navigator.clipboard.writeText(
      message.role === 'user' ? splitImageMessage(message.content).question : message.content,
    )
    copied.value = message.id
  } catch {
    copied.value = `failed:${message.id}`
  }
  clearTimeout(copyTimer)
  copyTimer = setTimeout(() => {
    copied.value = ''
  }, 1800)
}
watch(
  () => [props.messages.length, props.messages.at(-1)?.content, props.loading],
  async () => {
    await nextTick()
    if (props.isNew && !props.messages.length) {
      if (viewport.value) viewport.value.scrollTop = 0
      followBottom.value = true
      return
    }
    if (prependAnchor) {
      if (!props.loading && viewport.value) {
        viewport.value.scrollTop =
          prependAnchor.top + viewport.value.scrollHeight - prependAnchor.height
        prependAnchor = null
      }
    } else if (followBottom.value) bottom()
  },
  { immediate: true },
)
onBeforeUnmount(() => clearTimeout(copyTimer))
</script>

<template>
  <div class="message-stage">
    <div ref="viewport" class="message-viewport" @scroll.passive="onScroll">
      <div v-if="isNew && messages.length === 0" class="welcome-state">
        <div class="welcome-emblem" aria-hidden="true">
          <div class="emblem-ring"></div>
          <BrandMark compact /><span class="emblem-star">✦</span>
        </div>
        <div class="eyebrow welcome-eyebrow">YOUR INTELLIGENT SUPPORT COMPANION</div>
        <h1>
          你好，{{ customerName }}<span class="greeting-dot">.</span><br />有什么可以<span
            class="accent"
            >帮到你？</span
          >
        </h1>
        <p class="welcome-description">
          无论是一句提问，还是一张图片，<br class="mobile-only" />让我们一起找到答案。
        </p>
        <div class="modality-labels">
          <span><MessageSquare :size="13" />自然对话</span><i></i
          ><span><ScanLine :size="13" />图像理解</span><i></i
          ><span><Sparkles :size="13" />知识检索</span>
        </div>
        <div class="suggestion-grid">
          <button @click="emit('suggest', 'policy')">
            <span class="suggestion-icon"><Sparkles :size="20" /></span><strong>售后政策咨询</strong
            ><span>了解退换货与售后规则</span><span class="suggestion-arrow">↗</span></button
          ><button @click="emit('suggest', 'orders')">
            <span class="suggestion-icon"><ShoppingBag :size="20" /></span
            ><strong>订单与退款查询</strong><span>查看订单及退款进度</span
            ><span class="suggestion-arrow">↗</span></button
          ><button @click="emit('suggest', 'image')">
            <span class="suggestion-icon"><ScanLine :size="20" /></span><strong>上传图片提问</strong
            ><span>识别商品，辅助售后沟通</span><span class="suggestion-arrow">↗</span>
          </button>
        </div>
        <span class="welcome-coordinate" aria-hidden="true">01 / CONVERSATION INTERFACE</span>
      </div>
      <div v-else class="transcript">
        <button v-if="hasOlder" class="older-button" :disabled="loading || busy" @click="older">
          <ArrowUp :size="14" />{{ loading ? '正在加载…' : '加载更早的消息' }}
        </button>
        <div v-if="loading && !messages.length" class="history-loading">
          <span class="spinner"></span>正在读取聊天记录
        </div>
        <div v-if="error" class="inline-alert" role="alert">
          <TriangleAlert :size="16" /><span>{{ error }}</span
          ><button class="text-button" :disabled="loading || busy" @click="emit('retry')">
            重新加载
          </button>
        </div>
        <div v-if="!loading && !error && !messages.length" class="empty-history">
          <MessageSquare :size="28" />
          <p>这个会话还没有消息，发送一句话开始吧。</p>
        </div>
        <article
          v-for="message in messages"
          :key="message.id"
          class="chat-message"
          :class="message.role"
        >
          <div class="message-avatar">
            <BrandMark v-if="message.role === 'assistant'" compact /><span v-else>你</span>
          </div>
          <div class="message-main">
            <div class="message-meta">
              <strong>{{ message.role === 'assistant' ? 'OmniSupport' : '你' }}</strong
              ><span v-if="message.role === 'assistant'" class="ai-tag">AI</span
              ><time>{{ formatTime(message.created_at) }}</time
              ><span v-if="message.state === 'unconfirmed'" class="unconfirmed-tag"
                >保存状态未确认</span
              ><button
                v-if="message.content"
                class="icon-button copy-message"
                :aria-label="copied === message.id ? '已复制' : '复制消息'"
                :title="
                  copied === `failed:${message.id}`
                    ? '复制失败，请手动选择文本'
                    : copied === message.id
                      ? '已复制'
                      : '复制消息'
                "
                @click="copyMessage(message)"
              >
                <Check v-if="copied === message.id" :size="14" /><Copy v-else :size="14" />
              </button>
            </div>
            <template v-if="message.role === 'user'"
              ><a
                v-if="message.attachment"
                :href="message.attachment.url"
                target="_blank"
                rel="noopener noreferrer"
                class="message-image"
                ><img
                  :src="message.attachment.url"
                  :alt="message.attachment.name"
                  @load="followBottom && bottom()"
                /><span><Image :size="12" />{{ message.attachment.name }}</span></a
              >
              <p class="user-message-text">{{ splitImageMessage(message.content).question }}</p>
              <details
                v-if="splitImageMessage(message.content).observation"
                class="image-observation"
              >
                <summary><ScanLine :size="13" />图片观察记录 · AI 生成</summary>
                <MarkdownText
                  :content="splitImageMessage(message.content).observation || ''"
                /></details
            ></template>
            <template v-else
              ><MarkdownText v-if="message.content" :content="message.content" />
              <div
                v-if="message.state === 'pending' && !message.content"
                class="typing-indicator"
                role="status"
                aria-label="客服正在回复"
              >
                <span></span><span></span><span></span>
              </div>
              <div v-if="message.state === 'failed'" class="message-failure" role="alert">
                <TriangleAlert :size="15" /><span
                  >{{ message.error }}<small>本次结果未确认完成，建议先刷新记录核对。</small></span
                >
              </div>
              <span
                v-if="message.state === 'pending' && message.content"
                class="stream-cursor"
                aria-label="正在生成"
              ></span
            ></template>
          </div>
        </article>
        <div v-if="total > 0 && !busy" class="transcript-end">
          <span></span>当前已加载 {{ messages.length }} 条消息<span></span>
        </div>
      </div>
    </div>
    <button
      v-if="!followBottom && messages.length"
      class="scroll-to-bottom icon-button"
      aria-label="滚动到最新消息"
      @click="bottom"
    >
      <ArrowDown :size="18" />
    </button>
  </div>
</template>
