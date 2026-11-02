import { onBeforeUnmount, ref, shallowRef, watch, type Ref } from 'vue'
import { errorMessage, isAbort } from '../api/http'
export function usePage<T>(
  source: Ref<string>,
  load: (
    path: string,
    offset: number,
    signal: AbortSignal,
  ) => Promise<{ items: T[]; total: number }>,
) {
  const items = shallowRef<T[]>([]),
    total = ref(0),
    offset = ref(0),
    loading = ref(false),
    error = ref('')
  let controller: AbortController | undefined
  async function refresh(next = offset.value) {
    controller?.abort()
    const request = new AbortController()
    controller = request
    loading.value = true
    error.value = ''
    try {
      const data = await load(source.value, next, request.signal)
      if (controller !== request) return
      items.value = data.items
      total.value = data.total
      offset.value = next
    } catch (cause) {
      if (controller === request && !isAbort(cause)) error.value = errorMessage(cause)
    } finally {
      if (controller === request) loading.value = false
    }
  }
  watch(
    source,
    () => {
      items.value = []
      total.value = 0
      void refresh(0)
    },
    { immediate: true },
  )
  onBeforeUnmount(() => controller?.abort())
  return { items, total, offset, loading, error, refresh }
}
export function useAction() {
  const busy = ref(false),
    error = ref(''),
    notice = ref('')
  async function run(action: () => Promise<void>) {
    if (busy.value) return
    busy.value = true
    error.value = ''
    notice.value = ''
    try {
      await action()
    } catch (cause) {
      error.value = errorMessage(cause) + ' 如请求结果不明确，请先刷新核对。'
    } finally {
      busy.value = false
    }
  }
  return { busy, error, notice, run }
}
