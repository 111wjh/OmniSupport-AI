<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ArrowUp, ImagePlus, Radio, X, Image, LoaderCircle } from 'lucide-vue-next'
import { validateImage } from '../api/image'
import { errorMessage } from '../api/http'
import type { SendInput } from '../composables/useChat'

const props = defineProps<{
  busy: boolean
  disabled: boolean
  activity: string
  resetKey: number
}>()
const emit = defineEmits<{ send: [input: SendInput] }>()
const draft = ref('')
const file = ref<File | null>(null)
const preview = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const textarea = ref<HTMLTextAreaElement | null>(null)
const stream = ref(true)
const error = ref('')
const limit = computed(() => (file.value ? 1000 : 2000))
const blocked = computed(() => props.busy || props.disabled)
const canSend = computed(
  () => !blocked.value && draft.value.trim().length > 0 && draft.value.length <= limit.value,
)

function resize() {
  const element = textarea.value
  if (element) {
    element.style.height = 'auto'
    element.style.height = `${Math.min(element.scrollHeight, 164)}px`
  }
}
function setDraft(value: string) {
  if (blocked.value) return
  draft.value = value
  void nextTick(() => {
    resize()
    textarea.value?.focus()
  })
}
function openImagePicker() {
  if (!blocked.value) fileInput.value?.click()
}
function selectFile(value: File) {
  if (blocked.value) return
  try {
    validateImage(value)
    file.value = value
    error.value = ''
    if (!draft.value.trim()) setDraft('请分析这张图片中的商品，描述外观并说明是否能看到破损迹象。')
  } catch (cause) {
    error.value = errorMessage(cause)
  }
}
function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files?.[0]) selectFile(input.files[0])
  input.value = ''
}
function onDrop(event: DragEvent) {
  if (event.dataTransfer?.files[0]) selectFile(event.dataTransfer.files[0])
}
function submit() {
  if (!canSend.value) return
  error.value = ''
  emit('send', { text: draft.value.trim(), file: file.value, stream: stream.value })
}
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    submit()
  }
}
watch(file, (value) => {
  if (preview.value) URL.revokeObjectURL(preview.value)
  preview.value = value ? URL.createObjectURL(value) : ''
})
watch(
  () => props.resetKey,
  () => {
    draft.value = ''
    file.value = null
    error.value = ''
    void nextTick(resize)
  },
)
onBeforeUnmount(() => {
  if (preview.value) URL.revokeObjectURL(preview.value)
})
defineExpose({ setDraft, openImagePicker })
</script>

<template>
  <div class="composer-area">
    <form
      class="composer"
      :class="{ 'is-busy': busy, 'has-attachment': file }"
      @submit.prevent="submit"
      @dragover.prevent
      @drop.prevent="onDrop"
    >
      <div v-if="file" class="attachment-preview">
        <img :src="preview" :alt="file.name" />
        <div>
          <strong>{{ file.name }}</strong
          ><span><Image :size="12" />{{ (file.size / 1024).toFixed(0) }} KB · 图片问答</span>
        </div>
        <button
          class="icon-button"
          type="button"
          :disabled="blocked"
          aria-label="移除图片"
          @click="file = null"
        >
          <X :size="15" />
        </button>
      </div>
      <label class="sr-only" for="message-input">输入你的问题</label
      ><textarea
        id="message-input"
        ref="textarea"
        v-model="draft"
        rows="2"
        :maxlength="limit"
        :disabled="blocked"
        :placeholder="file ? '你想了解这张图片的哪些内容？' : '输入你的问题，或上传一张图片…'"
        @input="resize"
        @keydown="onKeydown"
      ></textarea>
      <div class="composer-toolbar">
        <div class="composer-tools">
          <input
            ref="fileInput"
            class="sr-only"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            tabindex="-1"
            aria-label="选择图片"
            @change="onFileChange"
          /><button
            class="icon-button upload-button"
            type="button"
            :disabled="blocked"
            aria-label="上传图片"
            title="上传 JPG、PNG、WEBP 图片，最大 5 MB"
            @click="openImagePicker"
          >
            <ImagePlus :size="19" /></button
          ><span class="toolbar-divider"></span
          ><button
            class="stream-toggle"
            type="button"
            :class="{ active: stream && !file }"
            :aria-pressed="stream && !file"
            :disabled="blocked || !!file"
            @click="stream = !stream"
          >
            <Radio :size="14" />{{ file ? '图片分析' : '流式回复'
            }}<span class="toggle-indicator"></span>
          </button>
        </div>
        <div class="composer-send-group">
          <span
            v-if="draft.length > limit * 0.8"
            class="character-count"
            :class="{ invalid: draft.length > limit }"
            >{{ draft.length }}/{{ limit }}</span
          ><span v-if="busy" class="sending-label">{{ activity }}…</span
          ><button class="send-button" type="submit" :disabled="!canSend" aria-label="发送消息">
            <LoaderCircle v-if="busy" :size="18" class="spinning" /><ArrowUp v-else :size="21" />
          </button>
        </div>
      </div>
    </form>
    <p v-if="error || draft.length > limit" class="composer-error" role="alert">
      {{ error || `图片问题不能超过 ${limit} 个字符，请缩短内容。` }}
    </p>
    <div class="composer-caption">
      <span>AI 回复供参考，业务结果以系统记录为准</span
      ><span class="keyboard-hint"
        ><kbd>Enter</kbd> 发送 <span>·</span> <kbd>Shift + Enter</kbd> 换行</span
      >
    </div>
  </div>
</template>
