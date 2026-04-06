import { ref } from 'vue'

/**
 * 操作反馈通知 composable
 * 在需要显示操作结果通知（成功/失败/警告）的页面共用
 */
export function useActionFeedback() {
  const actionNotice = ref(null)
  let _timer = null

  /**
   * 显示通知
   * @param {'ok'|'fail'|'warn'} tone
   * @param {string} title
   * @param {string} detail
   * @param {number} autoClearMs 自动清除时间（0 表示不清除）
   */
  function showNotice(tone, title, detail, autoClearMs = 6000) {
    actionNotice.value = { tone, title, detail, ts: Date.now() }
    if (_timer) clearTimeout(_timer)
    if (autoClearMs > 0) {
      _timer = setTimeout(() => { actionNotice.value = null }, autoClearMs)
    }
  }

  function clearNotice() {
    actionNotice.value = null
    if (_timer) clearTimeout(_timer)
  }

  return { actionNotice, showNotice, clearNotice }
}
