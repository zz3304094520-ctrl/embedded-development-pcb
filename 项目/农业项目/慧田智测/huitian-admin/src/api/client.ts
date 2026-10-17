const directBase = import.meta.env.VITE_API_BASE_URL || 'http://172.20.10.2:8000'
export const apiBaseUrl = import.meta.env.DEV ? '' : directBase.replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message)
    this.name = 'ApiError'
  }
}

function validationMessage(detail: unknown): string | null {
  if (!Array.isArray(detail)) return null
  return detail.map((item) => {
    if (!item || typeof item !== 'object') return '字段校验失败'
    const entry = item as { loc?: unknown[]; msg?: string }
    const field = entry.loc?.at(-1)
    return `${typeof field === 'string' ? field : '字段'}：${entry.msg || '格式不正确'}`
  }).join('；')
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: { Accept: 'application/json', ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...options.headers },
    ...options,
  })
  if (!response.ok) {
    let message = `请求失败（HTTP ${response.status}）`
    try {
      const body = await response.json() as { detail?: unknown }
      message = typeof body.detail === 'string' ? body.detail : validationMessage(body.detail) || message
    } catch { /* keep fallback */ }
    throw new ApiError(message, response.status)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') search.set(key, String(value))
  })
  return search.size ? `?${search}` : ''
}
