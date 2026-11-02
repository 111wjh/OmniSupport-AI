<script setup lang="ts">
defineProps<{ offset: number; total: number; loading: boolean }>()
defineEmits<{ page: [offset: number] }>()
</script>
<template>
  <footer class="desk-pagination">
    <span>共 {{ total }} 条 · {{ total ? offset + 1 : 0 }}–{{ Math.min(offset + 10, total) }}</span>
    <div>
      <button :disabled="loading || offset === 0" @click="$emit('page', Math.max(0, offset - 10))">
        上一页</button
      ><button :disabled="loading || offset + 10 >= total" @click="$emit('page', offset + 10)">
        下一页
      </button>
    </div>
  </footer>
</template>
