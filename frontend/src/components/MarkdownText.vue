<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps<{ content: string }>()
// 模型和历史消息都属于外部内容：解析 Markdown 后再按白名单清理 HTML。
const html = computed(() =>
  DOMPurify.sanitize(marked.parse(props.content, { async: false, breaks: true, gfm: true }), {
    ALLOWED_TAGS: [
      'p',
      'br',
      'strong',
      'em',
      'del',
      'ul',
      'ol',
      'li',
      'h1',
      'h2',
      'h3',
      'h4',
      'h5',
      'h6',
      'blockquote',
      'pre',
      'code',
      'a',
      'table',
      'thead',
      'tbody',
      'tr',
      'th',
      'td',
      'hr',
    ],
    ALLOWED_ATTR: ['href', 'title', 'start'],
  }),
)
</script>

<template><div class="markdown" v-html="html"></div></template>
