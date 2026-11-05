<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  page,
  post,
  record,
  isRefund,
  isExecution,
  label,
  money,
  date,
  type Refund,
  type Execution,
} from '../api/business'
import { usePage, useAction } from '../composables/useBusiness'
import PageControls from './PageControls.vue'
const props = defineProps<{ token: string; staff?: boolean }>()
const staffQueue = ref<'pending' | 'ready'>('pending')
const showingReady = computed(() => !!props.staff && staffQueue.value === 'ready')
const source = computed(() => {
  if (!props.staff) return '/api/v1/refunds'
  return showingReady.value ? '/api/v1/refunds/ready-to-execute' : '/api/v1/refunds/pending'
})
const { items, total, offset, loading, error, refresh } = usePage(source, (p, o, s) =>
  page(p, props.token, isRefund, o, s),
)
const action = useAction(),
  selected = ref<Refund | null>(null),
  comment = ref(''),
  executionTarget = ref<Refund | null>(null),
  execution = ref<Execution | null>(null)
function selectQueue(queue: 'pending' | 'ready') {
  if (staffQueue.value === queue) return
  staffQueue.value = queue
  selected.value = null
  comment.value = ''
  executionTarget.value = null
  execution.value = null
  action.notice.value = ''
  action.error.value = ''
}
function selectExecution(item: Refund) {
  executionTarget.value = item
  execution.value = null
  action.notice.value = ''
  action.error.value = ''
}
function selectRefund(item: Refund) {
  selected.value = item
  comment.value = ''
}
async function review(decision: 'approved' | 'rejected') {
  if (!selected.value) return
  await action.run(async () => {
    const result = await post(
      '/api/v1/refunds/' + selected.value!.id + '/review',
      props.token,
      isRefund,
      { decision, review_comment: comment.value.trim() },
    )
    action.notice.value =
      result.status === 'approved'
        ? '审核通过。请到待执行队列核对并执行模拟退款。'
        : '审核结果：' + label(result.status) + '。'
    selected.value = null
    comment.value = ''
    await refresh()
  })
}
async function execute() {
  const target = executionTarget.value
  if (!target) return
  await action.run(async () => {
    execution.value = await post(
      '/api/v1/refunds/' + encodeURIComponent(target.id) + '/execute',
      props.token,
      isExecution,
    )
    executionTarget.value = null
    action.notice.value = '模拟退款执行结果已返回，请查看记录。'
    await refresh(0)
  })
}
async function lookup(id: string) {
  execution.value = null
  await action.run(async () => {
    execution.value = await record('/api/v1/refunds/' + id + '/execution', props.token, isExecution)
  })
}
</script>
<template>
  <section class="desk-section">
    <div class="desk-toolbar">
      <div>
        <span class="eyebrow">AFTER-SALES CONTROL</span>
        <h1>{{ staff ? '退款审核' : '我的退款' }}</h1>
        <p>申请、审核与模拟执行分开处理，状态来自业务接口。</p>
      </div>
      <button :disabled="loading || action.busy.value" @click="refresh()">刷新记录</button>
    </div>
    <div v-if="staff" class="desk-filters" aria-label="退款队列">
      <button
        type="button"
        :class="{ active: !showingReady }"
        :aria-pressed="!showingReady"
        :disabled="action.busy.value"
        @click="selectQueue('pending')"
      >
        待审核队列
      </button>
      <button
        type="button"
        :class="{ active: showingReady }"
        :aria-pressed="showingReady"
        :disabled="action.busy.value"
        @click="selectQueue('ready')"
      >
        待执行队列
      </button>
    </div>
    <p class="desk-disclaimer">演示模式 · 本项目未接入真实支付网关，执行成功不代表资金实际到账。</p>
    <p v-if="error || action.error.value" role="alert" class="desk-error">
      {{ error || action.error.value }}
    </p>
    <p v-if="action.notice.value" class="desk-notice" role="status">{{ action.notice.value }}</p>
    <div v-if="loading" class="desk-empty">正在读取退款记录…</div>
    <div v-else-if="!items.length && !error" class="desk-empty">
      {{
        staff
          ? showingReady
            ? '暂无待执行的退款申请。'
            : '暂无待审核申请。'
          : '暂无退款申请，可从订单页面发起。'
      }}
    </div>
    <div class="desk-grid">
      <article v-for="item in items" :key="item.id" class="desk-card">
        <div class="desk-card-top">
          <span>退款申请</span
          ><span class="desk-badge" :data-status="item.status">{{ label(item.status) }}</span>
        </div>
        <code>{{ item.id }}</code>
        <h2>{{ item.order_number || '订单 ' + item.order_id.slice(0, 8) }}</h2>
        <p v-if="item.customer_email">
          {{ item.customer_email }} · {{ money(item.order_total_amount) }}
        </p>
        <p class="desk-prose">{{ item.reason }}</p>
        <p>{{ date(item.requested_at) }}</p>
        <p v-if="item.review_comment">审核意见：{{ item.review_comment }}</p>
        <button
          v-if="showingReady"
          :disabled="action.busy.value || loading"
          @click="selectExecution(item)"
        >
          选择执行 →
        </button>
        <button v-else-if="staff" :disabled="action.busy.value" @click="selectRefund(item)">
          审核此申请 →
        </button>
        <button v-else :disabled="action.busy.value" @click="lookup(item.id)">
          查询模拟执行结果 →
        </button>
      </article>
    </div>
    <PageControls
      :offset="offset"
      :total="total"
      :loading="loading || action.busy.value"
      @page="refresh"
    />
    <form v-if="selected" class="desk-detail desk-form" @submit.prevent="review('approved')">
      <h2>审核申请 {{ selected.id.slice(0, 8) }}</h2>
      <label>审核意见<textarea v-model="comment" required maxlength="2000" rows="3" /></label>
      <div class="desk-actions">
        <button class="primary-button" :disabled="action.busy.value || !comment.trim()">
          审核通过</button
        ><button
          type="button"
          :disabled="action.busy.value || !comment.trim()"
          @click="review('rejected')"
        >
          拒绝申请</button
        ><button type="button" :disabled="action.busy.value" @click="selected = null">取消</button>
      </div>
    </form>
    <form v-if="executionTarget" class="desk-detail desk-form" @submit.prevent="execute">
      <h2>核对并执行模拟退款</h2>
      <p>
        订单 {{ executionTarget.order_number || executionTarget.order_id }} ·
        {{ money(executionTarget.order_total_amount) }}
      </p>
      <p>
        退款申请编号 <code>{{ executionTarget.id }}</code>
      </p>
      <div class="desk-actions">
        <button class="primary-button" :disabled="action.busy.value">确认模拟退款</button>
        <button type="button" :disabled="action.busy.value" @click="executionTarget = null">
          取消
        </button>
      </div>
    </form>
    <div v-if="execution" class="desk-detail" role="status">
      <h2>模拟执行记录</h2>
      <p>
        {{ label(execution.status) }} · {{ money(execution.amount) }} ·
        {{ date(execution.executed_at) }}
      </p>
      <code>{{ execution.refund_request_id }}</code>
      <p class="desk-disclaimer">仅为模拟业务执行结果。</p>
    </div>
  </section>
</template>
