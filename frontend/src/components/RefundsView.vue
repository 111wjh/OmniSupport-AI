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
const source = computed(() => (props.staff ? '/api/v1/refunds/pending' : '/api/v1/refunds'))
const { items, total, offset, loading, error, refresh } = usePage(source, (p, o, s) =>
  page(p, props.token, isRefund, o, s),
)
const action = useAction(),
  selected = ref<Refund | null>(null),
  comment = ref(''),
  executionId = ref(''),
  execution = ref<Execution | null>(null)
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
    if (result.status === 'approved') executionId.value = result.id
    action.notice.value = '审核结果：' + label(result.status) + '。审核通过后仍需单独执行模拟退款。'
    selected.value = null
    comment.value = ''
    await refresh()
  })
}
async function execute() {
  await action.run(async () => {
    execution.value = await post(
      '/api/v1/refunds/' + encodeURIComponent(executionId.value.trim()) + '/execute',
      props.token,
      isExecution,
    )
    action.notice.value = '模拟退款执行结果已返回，请查看记录。'
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
    <p class="desk-disclaimer">演示模式 · 本项目未接入真实支付网关，执行成功不代表资金实际到账。</p>
    <p v-if="error || action.error.value" role="alert" class="desk-error">
      {{ error || action.error.value }}
    </p>
    <p v-if="action.notice.value" class="desk-notice" role="status">{{ action.notice.value }}</p>
    <div v-if="loading" class="desk-empty">正在读取退款记录…</div>
    <div v-else-if="!items.length && !error" class="desk-empty">
      {{
        staff
          ? '暂无待审核申请。已审核的申请不会继续出现在待审队列。'
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
        <button v-if="staff" :disabled="action.busy.value" @click="selectRefund(item)">
          审核此申请 →</button
        ><button v-else :disabled="action.busy.value" @click="lookup(item.id)">
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
    <form v-if="staff" class="desk-detail desk-form" @submit.prevent="execute">
      <h2>执行已通过的模拟退款</h2>
      <p>审核通过不会自动退款。请核对申请编号后单独执行；可粘贴此前已审核申请的编号。</p>
      <label
        >退款申请编号<input
          v-model="executionId"
          required
          pattern="[0-9a-fA-F-]{36}"
          placeholder="已审核通过的退款申请 UUID" /></label
      ><button class="primary-button" :disabled="action.busy.value || !executionId.trim()">
        执行模拟退款
      </button>
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
