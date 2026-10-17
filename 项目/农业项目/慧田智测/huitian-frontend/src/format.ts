export function formatNumber(value: number, digits = 1): string {
  if (!Number.isFinite(value)) return '--'
  return new Intl.NumberFormat('zh-CN', {
    maximumFractionDigits: digits,
    minimumFractionDigits: Number.isInteger(value) ? 0 : Math.min(digits, 1),
  }).format(value)
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '暂无'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '时间格式异常'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function relativeStatusTime(value: string | null | undefined): string {
  if (!value) return '从未上报'
  const date = new Date(value)
  const diff = Date.now() - date.getTime()
  if (Number.isNaN(diff)) return '时间异常'
  const minutes = Math.max(0, Math.round(diff / 60000))
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  return `${Math.round(hours / 24)} 天前`
}

export function hasRecentHeartbeat(
  isOnline: boolean,
  lastSeenAt: string | null | undefined,
  maxAgeMs = 45_000,
): boolean {
  if (!isOnline || !lastSeenAt) return false
  const timestamp = new Date(lastSeenAt).getTime()
  if (Number.isNaN(timestamp)) return false
  return Date.now() - timestamp <= maxAgeMs
}
