<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowDown, MessageSquare, RefreshCw, Search, SearchX } from 'lucide-vue-next'
import type { ConversationSummary } from '../api/conversation'
import { conversationTitle, formatDate } from '../utils/format'

const props = defineProps<{
  items: ConversationSummary[]
  total: number
  loading: boolean
  error: string
  hasMore: boolean
  activeId: string | null
  disabled: boolean
  previews: Record<string, string>
}>()
const emit = defineEmits<{ select: [id: string]; more: []; refresh: [] }>()
const search = ref('')
function titleFor(item: ConversationSummary): string {
  return item.title && item.title !== '新会话'
    ? item.title
    : props.previews[item.id] || conversationTitle(item.title, item.updated_at)
}
const filtered = computed(() => {
  const query = search.value.trim().toLowerCase()
  return props.items.filter((item) =>
    `${item.title} ${props.previews[item.id] || ''} ${formatDate(item.updated_at)}`
      .toLowerCase()
      .includes(query),
  )
})
</script>

<template>
  <div class="conversation-list">
    <label class="sidebar-search"
      ><Search :size="15" /><input
        v-model="search"
        placeholder="搜索已加载会话"
        aria-label="搜索已加载会话"
      /><kbd>⌕</kbd></label
    >
    <div class="sidebar-section-label">
      <span
        >最近对话 <span class="count-badge">{{ total }}</span></span
      ><button
        class="icon-button"
        aria-label="刷新会话列表"
        title="刷新列表"
        :disabled="loading || disabled"
        @click="emit('refresh')"
      >
        <RefreshCw :size="13" :class="{ spinning: loading }" />
      </button>
    </div>
    <div class="conversation-scroll">
      <div v-if="loading && !items.length" class="list-skeleton" aria-label="正在加载会话">
        <span v-for="n in 4" :key="n"></span>
      </div>
      <div v-if="error" class="sidebar-error" role="alert">
        <p>{{ error }}</p>
        <button class="text-button" :disabled="loading || disabled" @click="emit('refresh')">
          重新加载
        </button>
      </div>
      <div v-if="!loading && !error && !filtered.length" class="sidebar-empty">
        <SearchX :size="25" />
        <p>{{ search ? '没有匹配的已加载会话' : '还没有历史会话' }}</p>
        <span>{{ search ? '试试其他关键词，或加载更多' : '从一条新对话开始吧' }}</span>
      </div>
      <button
        v-for="item in filtered"
        :key="item.id"
        class="conversation-item"
        :class="{ active: activeId === item.id }"
        :aria-pressed="activeId === item.id"
        :disabled="disabled"
        @click="emit('select', item.id)"
      >
        <MessageSquare :size="16" /><span class="conversation-item-body"
          ><span class="conversation-title">{{ titleFor(item) }}</span
          ><span class="conversation-date">{{ formatDate(item.updated_at) }}</span></span
        ><span v-if="activeId === item.id" class="selected-indicator"></span>
      </button>
      <button
        v-if="hasMore"
        class="load-more"
        :disabled="loading || disabled"
        @click="emit('more')"
      >
        <ArrowDown :size="13" />{{ loading ? '正在加载…' : '加载更多会话' }}
      </button>
    </div>
    <p class="sidebar-history-note">会话仅对当前登录账号可见</p>
  </div>
</template>
