import { onBeforeUnmount, onMounted, readonly, ref } from 'vue'

export type CurrentWeather = {
  temperature: number
  humidity: number
  apparentTemperature: number
  weatherCode: number
  observedAt: string
}

type OpenMeteoResponse = {
  current?: {
    temperature_2m?: number
    relative_humidity_2m?: number
    apparent_temperature?: number
    weather_code?: number
    time?: string
  }
}

const HANGZHOU_WEATHER_URL = new URL('https://api.open-meteo.com/v1/forecast')
HANGZHOU_WEATHER_URL.search = new URLSearchParams({
  latitude: '30.2741',
  longitude: '120.1551',
  current: 'temperature_2m,relative_humidity_2m,apparent_temperature,weather_code',
  temperature_unit: 'celsius',
  timezone: 'Asia/Shanghai',
}).toString()

const REFRESH_INTERVAL_MS = 10 * 60 * 1000
const REQUEST_TIMEOUT_MS = 8_000

function parseCurrentWeather(payload: OpenMeteoResponse): CurrentWeather {
  const current = payload.current
  if (
    !current ||
    !Number.isFinite(current.temperature_2m) ||
    !Number.isFinite(current.relative_humidity_2m) ||
    !Number.isFinite(current.apparent_temperature) ||
    !Number.isFinite(current.weather_code) ||
    !current.time
  ) {
    throw new Error('天气服务返回的数据不完整')
  }

  return {
    temperature: current.temperature_2m as number,
    humidity: current.relative_humidity_2m as number,
    apparentTemperature: current.apparent_temperature as number,
    weatherCode: current.weather_code as number,
    observedAt: `${current.time}:00+08:00`,
  }
}

export function weatherCodeLabel(code: number): string {
  if (code === 0) return '晴'
  if (code === 1) return '大致晴朗'
  if (code === 2) return '多云'
  if (code === 3) return '阴'
  if (code === 45 || code === 48) return '有雾'
  if (code >= 51 && code <= 57) return '毛毛雨'
  if (code >= 61 && code <= 67) return '有雨'
  if (code >= 71 && code <= 77) return '有雪'
  if (code >= 80 && code <= 82) return '阵雨'
  if (code === 85 || code === 86) return '阵雪'
  if (code >= 95 && code <= 99) return '雷雨'
  return '天气变化中'
}

export function useHangzhouWeather() {
  const currentWeather = ref<CurrentWeather | null>(null)
  const weatherLoading = ref(true)
  const weatherError = ref<string | null>(null)
  let refreshTimer: number | null = null
  let activeController: AbortController | null = null

  async function refreshWeather(): Promise<void> {
    activeController?.abort()
    const controller = new AbortController()
    activeController = controller
    const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

    try {
      weatherLoading.value = true
      const response = await fetch(HANGZHOU_WEATHER_URL, {
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      })
      if (!response.ok) {
        throw new Error(`天气服务请求失败（${response.status}）`)
      }

      currentWeather.value = parseCurrentWeather((await response.json()) as OpenMeteoResponse)
      weatherError.value = null
    } catch (error) {
      if (controller.signal.aborted && activeController !== controller) return
      weatherError.value =
        error instanceof DOMException && error.name === 'AbortError'
          ? '获取杭州天气超时'
          : error instanceof Error
            ? error.message
            : '暂时无法获取杭州天气'
    } finally {
      window.clearTimeout(timeout)
      if (activeController === controller) {
        activeController = null
        weatherLoading.value = false
      }
    }
  }

  onMounted(() => {
    void refreshWeather()
    refreshTimer = window.setInterval(() => {
      void refreshWeather()
    }, REFRESH_INTERVAL_MS)
  })

  onBeforeUnmount(() => {
    activeController?.abort()
    if (refreshTimer !== null) {
      window.clearInterval(refreshTimer)
      refreshTimer = null
    }
  })

  return {
    currentWeather: readonly(currentWeather),
    weatherLoading: readonly(weatherLoading),
    weatherError: readonly(weatherError),
    refreshWeather,
  }
}
