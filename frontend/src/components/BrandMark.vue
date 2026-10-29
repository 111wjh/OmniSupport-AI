<script setup lang="ts">
defineProps<{ compact?: boolean }>()
</script>

<template>
  <div class="brand" :class="{ compact }">
    <span class="brand-symbol" aria-hidden="true"><span></span><span></span><span></span></span>
    <span v-if="!compact" class="brand-wordmark">omni<span>SUPPORT AI</span></span>
  </div>
</template>
