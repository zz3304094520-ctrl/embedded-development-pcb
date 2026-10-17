import { shallowRef } from 'vue'

export function useAsyncState() {
  const loading = shallowRef(false)
  const error = shallowRef('')
  async function run<T>(task: () => Promise<T>): Promise<T | undefined> {
    loading.value = true
    error.value = ''
    try { return await task() }
    catch (reason) { error.value = reason instanceof Error ? reason.message : '请求失败，请稍后重试'; return undefined }
    finally { loading.value = false }
  }
  return { loading, error, run }
}
