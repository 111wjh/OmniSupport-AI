<script setup lang="ts">
import { ref } from 'vue'
import {
  isOrder,
  isRefund,
  page,
  post,
  label,
  date,
  money,
  record,
  type Order,
} from '../api/business'
import { usePage, useAction } from '../composables/useBusiness'
import PageControls from './PageControls.vue'
const props = defineProps<{ token: string }>()
const { items, total, offset, loading, error, refresh } = usePage(
  ref('/api/v1/orders'),
  (path, offset, signal) => page(path, props.token, isOrder, offset, signal),
)
const selected = ref<Order | null>(null),
  reason = ref('')
const action = useAction()
async function open(order: Order) {
  await action.run(async () => {
    selected.value = await record(
      '/api/v1/orders/' + encodeURIComponent(order.order_number),
      props.token,
      isOrder,
    )
    reason.value = ''
  })
}
async function submit() {
  if (!selected.value) return
  await action.run(async () => {
    const result = await post('/api/v1/refunds', props.token, isRefund, {
      order_number: selected.value!.order_number,
      reason: reason.value.trim(),
    })
    action.notice.value =
      '退款申请已提交，申请编号：' + result.id + '。后续需人工审核及单独模拟执行。'
    selected.value = null
    await refresh()
  })
}
</script>
<template>
  <section class="desk-section">
    <div class="desk-toolbar">
      <div>
        <span class="eyebrow">ORDER INTELLIGENCE</span>
        <h1>我的订单</h1>
        <p>查看订单，发起有记录、可追踪的售后申请。</p>
      </div>
      <button :disabled="loading || action.busy.value" @click="refresh()">刷新订单</button>
    </div>
    <p v-if="error || action.error.value" class="desk-error" role="alert">
      {{ error || action.error.value }}
    </p>
    <p v-if="action.notice.value" class="desk-notice" role="status">{{ action.notice.value }}</p>
    <div v-if="loading" class="desk-empty">正在加载订单…</div>
    <div v-else-if="!items.length && !error" class="desk-empty">
      暂无订单。演示订单可通过项目的本地命令准备。
    </div>
    <div class="desk-grid">
      <article v-for="order in items" :key="order.id" class="desk-card">
        <div class="desk-card-top">
          <span class="desk-icon">◈</span
          ><span class="desk-badge" :data-status="order.status">{{ label(order.status) }}</span>
        </div>
        <h2>{{ order.product_name }}</h2>
        <code>{{ order.order_number }}</code
        ><strong class="desk-amount">{{ money(order.total_amount) }}</strong>
        <p>{{ date(order.purchased_at) }}</p>
        <button :disabled="action.busy.value" @click="open(order)">查看详情与售后 →</button>
      </article>
    </div>
    <PageControls
      :offset="offset"
      :total="total"
      :loading="loading || action.busy.value"
      @page="refresh"
    />
    <section v-if="selected" class="desk-detail">
      <div class="desk-toolbar">
        <h2>订单详情</h2>
        <button :disabled="action.busy.value" @click="selected = null">收起</button>
      </div>
      <p>
        {{ selected.product_name }} · {{ money(selected.total_amount) }} ·
        {{ label(selected.status) }}
      </p>
      <code>{{ selected.id }}</code>
      <form v-if="selected.status === 'paid'" class="desk-form" @submit.prevent="submit">
        <label
          >退款原因<textarea
            v-model="reason"
            required
            minlength="5"
            maxlength="2000"
            rows="3"
            placeholder="请说明具体原因，至少 5 个字符"
          />
        </label>
        <p>提交后进入人工审核，当前项目执行的是模拟退款。</p>
        <button class="primary-button" :disabled="action.busy.value || reason.trim().length < 5">
          {{ action.busy.value ? '正在提交…' : '提交退款申请' }}
        </button>
      </form>
    </section>
  </section>
</template>
