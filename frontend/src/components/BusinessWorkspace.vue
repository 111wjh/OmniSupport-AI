<script setup lang="ts">
import { computed, ref } from 'vue'
import OrdersView from './OrdersView.vue'
import RefundsView from './RefundsView.vue'
import TicketsView from './TicketsView.vue'
import type { Staff } from '../api/business'
const props = defineProps<{
  token: string
  staff?: Staff
  view?: 'orders' | 'refunds' | 'tickets'
}>()
const staffTab = ref('tickets')
const roleNames = { admin: '管理员', customer_support: '人工客服', refund_reviewer: '退款审核员' }
const canTickets = computed(
  () => !props.staff || ['admin', 'customer_support'].includes(props.staff.role),
)
const canRefunds = computed(
  () => !props.staff || ['admin', 'refund_reviewer'].includes(props.staff.role),
)
const current = computed(() =>
  props.staff
    ? canTickets.value && canRefunds.value
      ? staffTab.value
      : canTickets.value
        ? 'tickets'
        : 'refunds'
    : props.view,
)
</script>
<template>
  <main class="service-desk">
    <div v-if="staff" class="desk-rolebar">
      <span>员工身份 · {{ staff.display_name }} · {{ roleNames[staff.role] }}</span>
      <div class="desk-filters">
        <button
          v-if="canTickets"
          :class="{ active: current === 'tickets' }"
          @click="staffTab = 'tickets'"
        >
          工单服务</button
        ><button
          v-if="canRefunds"
          :class="{ active: current === 'refunds' }"
          @click="staffTab = 'refunds'"
        >
          退款审核
        </button>
      </div>
    </div>
    <OrdersView v-if="current === 'orders' && !staff" :token="token" /><RefundsView
      v-else-if="current === 'refunds' && canRefunds"
      :token="token"
      :staff="!!staff"
    /><TicketsView
      v-else-if="current === 'tickets' && canTickets"
      :token="token"
      :staff="!!staff"
    />
  </main>
</template>
