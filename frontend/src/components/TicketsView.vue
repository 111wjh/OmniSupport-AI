<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  page,
  record,
  post,
  isTicket,
  isMessage,
  label,
  date,
  type Ticket,
  type TicketMessage,
} from '../api/business'
import { usePage, useAction } from '../composables/useBusiness'
import { errorMessage, isAbort } from '../api/http'
import PageControls from './PageControls.vue'
import { getChatIdentity, forgetChatIdentity } from '../api/chatIdentity'
const props = defineProps<{ token: string; staff?: boolean }>()
const queue = ref(true),
  status = ref(''),
  selected = ref<Ticket | null>(null),
  messages = ref<TicketMessage[]>([]),
  messageOffset = ref(0),
  messageTotal = ref(0),
  messageLoading = ref(false),
  messageError = ref('')
const source = computed(() => {
  const path = props.staff
    ? queue.value
      ? '/api/v1/staff/tickets/queue'
      : '/api/v1/staff/tickets/mine'
    : '/api/v1/tickets'
  return status.value && !(props.staff && queue.value) ? path + '?status=' + status.value : path
})
const { items, total, offset, loading, error, refresh } = usePage(source, (p, o, s) =>
  page(p, props.token, isTicket, o, s),
)
const action = useAction(),
  creating = ref(false),
  subject = ref(''),
  description = ref(''),
  order = ref(''),
  conversation = ref(''),
  reply = ref('')
let detailRequest: AbortController | undefined
watch(source, () => {
  detailRequest?.abort()
  selected.value = null
  messages.value = []
  messageError.value = ''
  messageLoading.value = false
})
onBeforeUnmount(() => detailRequest?.abort())
function showQueue() {
  queue.value = true
  status.value = ''
}
function hideDetail() {
  selected.value = null
  detailRequest?.abort()
}
async function history(next = 0) {
  if (!selected.value) return
  detailRequest?.abort()
  const request = new AbortController()
  detailRequest = request
  const id = selected.value.id
  messageLoading.value = true
  messageError.value = ''
  try {
    const data = await page(
      (props.staff ? '/api/v1/staff/tickets/' : '/api/v1/tickets/') + id + '/messages',
      props.token,
      isMessage,
      next,
      request.signal,
    )
    if (detailRequest !== request) return
    messages.value = data.items
    messageTotal.value = data.total
    messageOffset.value = next
  } catch (cause) {
    if (detailRequest === request && !isAbort(cause)) messageError.value = errorMessage(cause)
  } finally {
    if (detailRequest === request) messageLoading.value = false
  }
}
async function open(ticket: Ticket) {
  await action.run(async () => {
    detailRequest?.abort()
    selected.value = null
    messages.value = []
    reply.value = ''
    selected.value = await record(
      (props.staff ? '/api/v1/staff/tickets/' : '/api/v1/tickets/') + ticket.id,
      props.token,
      isTicket,
    )
    await history()
  })
}
async function claim(ticket: Ticket) {
  await action.run(async () => {
    const result = await post(
      '/api/v1/staff/tickets/' + ticket.id + '/claim',
      props.token,
      isTicket,
    )
    action.notice.value = '工单已由你领取。'
    queue.value = false
    await refresh(0)
    selected.value = result
    await history()
  })
}
async function create() {
  await action.run(async () => {
    const data = {
      subject: subject.value.trim(),
      description: description.value.trim(),
      order_number: order.value.trim() || null,
      conversation_id: conversation.value.trim() || null,
    }
    const body = JSON.stringify(data)
    const identity = await getChatIdentity(props.token, null, 'ticket-create:' + body, null)
    const ticket = await post('/api/v1/tickets', props.token, isTicket, data, {
      'Idempotency-Key': identity.requestId,
    })
    forgetChatIdentity(identity.storageKey)
    creating.value = false
    subject.value = ''
    description.value = ''
    order.value = ''
    conversation.value = ''
    action.notice.value =
      '工单已创建，编号：' + ticket.id + '。等待工作人员领取，后续通过工单记录沟通。'
    await refresh(0)
  })
}
async function sendReply() {
  if (!selected.value) return
  await action.run(async () => {
    await post(
      (props.staff ? '/api/v1/staff/tickets/' : '/api/v1/tickets/') +
        selected.value!.id +
        '/messages',
      props.token,
      isMessage,
      { content: reply.value.trim() },
    )
    reply.value = ''
    action.notice.value = '回复已提交。'
    await history(Math.floor(messageTotal.value / 10) * 10)
  })
}
async function close() {
  if (!selected.value) return
  await action.run(async () => {
    selected.value = await post(
      '/api/v1/staff/tickets/' + selected.value!.id + '/close',
      props.token,
      isTicket,
    )
    action.notice.value = '工单已关闭，双方仍可读取历史，无法继续追加回复。'
    await refresh()
    await history()
  })
}
</script>
<template>
  <section class="desk-section">
    <div class="desk-toolbar">
      <div>
        <span class="eyebrow">HUMAN SUPPORT NETWORK</span>
        <h1>{{ staff ? '人工服务工作台' : '我的人工工单' }}</h1>
        <p>AI 与人工协作，问题有归属，沟通有记录。</p>
      </div>
      <div class="desk-actions">
        <button :disabled="loading || action.busy.value" @click="refresh()">刷新列表</button
        ><button
          v-if="!staff"
          class="primary-button"
          :disabled="action.busy.value"
          @click="creating = !creating"
        >
          ＋ 新建工单
        </button>
      </div>
    </div>
    <div class="desk-filters">
      <template v-if="staff"
        ><button :class="{ active: queue }" :disabled="action.busy.value" @click="showQueue">
          待领取队列</button
        ><button :class="{ active: !queue }" :disabled="action.busy.value" @click="queue = false">
          我的工单
        </button></template
      ><select
        v-if="!staff || !queue"
        v-model="status"
        :disabled="action.busy.value"
        aria-label="按工单状态筛选"
      >
        <option value="">全部状态</option>
        <option value="open" v-if="!staff">待领取</option>
        <option value="in_progress">处理中</option>
        <option value="closed">已关闭</option>
      </select>
    </div>
    <p v-if="error || action.error.value" class="desk-error" role="alert">
      {{ error || action.error.value }}
    </p>
    <p v-if="action.notice.value" class="desk-notice" role="status">{{ action.notice.value }}</p>
    <form v-if="creating" class="desk-detail desk-form" @submit.prevent="create">
      <h2>申请人工协助</h2>
      <label>问题标题<input v-model="subject" required maxlength="200" /></label
      ><label
        >问题描述<textarea
          v-model="description"
          required
          minlength="5"
          maxlength="4000"
          rows="4"
        /></label
      ><label>关联订单号（可选）<input v-model="order" maxlength="50" /></label
      ><label
        >关联会话编号（可选）<input v-model="conversation" pattern="[0-9a-fA-F-]{36}"
      /></label>
      <p>重复提交相同内容会复用本次请求编号。创建成功后等待工作人员领取。</p>
      <button
        class="primary-button"
        :disabled="action.busy.value || description.trim().length < 5 || !subject.trim()"
      >
        提交工单
      </button>
    </form>
    <div v-if="loading" class="desk-empty">正在同步工单…</div>
    <div v-else-if="!items.length && !error" class="desk-empty">当前条件下没有工单。</div>
    <div class="desk-grid">
      <article v-for="ticket in items" :key="ticket.id" class="desk-card">
        <div class="desk-card-top">
          <span class="mono">{{ ticket.id.slice(0, 8) }}</span
          ><span class="desk-badge" :data-status="ticket.status">{{ label(ticket.status) }}</span>
        </div>
        <h2>{{ ticket.subject }}</h2>
        <p class="desk-prose">{{ ticket.description }}</p>
        <p>{{ date(ticket.created_at) }}</p>
        <button v-if="staff && queue" :disabled="action.busy.value" @click="claim(ticket)">
          领取并开始处理 →</button
        ><button v-else :disabled="action.busy.value" @click="open(ticket)">查看沟通记录 →</button>
      </article>
    </div>
    <PageControls
      :offset="offset"
      :total="total"
      :loading="loading || action.busy.value"
      @page="refresh"
    />
    <section v-if="selected" class="desk-detail">
      <button :disabled="action.busy.value" @click="open(selected)">刷新工单与记录</button>
      <div class="desk-toolbar">
        <div>
          <h2>{{ selected.subject }}</h2>
          <code>{{ selected.id }}</code>
        </div>
        <button :disabled="action.busy.value" @click="hideDetail">收起</button>
      </div>
      <p>{{ label(selected.status) }} · {{ selected.description }}</p>
      <p v-if="selected.order_id">
        关联订单：<code>{{ selected.order_id }}</code>
      </p>
      <p v-if="selected.conversation_id">
        关联会话：<code>{{ selected.conversation_id }}</code>
      </p>
      <p v-if="messageError" role="alert" class="desk-error">
        {{ messageError }} <button @click="history()">重新读取</button>
      </p>
      <p v-if="messageLoading">正在读取沟通记录…</p>
      <p v-else-if="!messages.length && !messageError" class="desk-empty">暂无沟通记录。</p>
      <div class="ticket-thread">
        <article v-for="message in messages" :key="message.id" :class="message.sender_type">
          <strong
            >{{ message.sender_type === 'staff' ? '人工客服' : '客户' }}
            <small>#{{ message.message_seq }} · {{ date(message.created_at) }}</small></strong
          >
          <p>{{ message.content }}</p>
        </article>
      </div>
      <PageControls
        :offset="messageOffset"
        :total="messageTotal"
        :loading="messageLoading || action.busy.value"
        @page="history"
      />
      <form v-if="selected.status !== 'closed'" class="desk-form" @submit.prevent="sendReply">
        <label>补充回复<textarea v-model="reply" required maxlength="4000" rows="3" /></label>
        <div class="desk-actions">
          <button
            class="primary-button"
            :disabled="action.busy.value || messageLoading || !!messageError || !reply.trim()"
          >
            发送回复</button
          ><button v-if="staff" type="button" :disabled="action.busy.value" @click="close">
            关闭此工单
          </button>
        </div>
        <p>回复失败时请先刷新记录核对，再决定是否重发。</p>
      </form>
      <p v-else class="desk-notice">工单已关闭，沟通记录已保留。</p>
    </section>
  </section>
</template>
