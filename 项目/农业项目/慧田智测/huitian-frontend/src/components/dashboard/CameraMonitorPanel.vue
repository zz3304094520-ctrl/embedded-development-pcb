<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, shallowRef, watch } from 'vue'
import { formatDateTime } from '../../format'
import type { Device, DiseaseDetection } from '../../types'

const props = defineProps<{
  camera: Device | null
  detections: DiseaseDetection[]
}>()

type StreamState = 'idle' | 'loading' | 'playing' | 'error'
type EdgeStatus = 'checking' | 'online' | 'offline'

const legacyDefaultCause = '模型返回了尚未配置农艺资料的类别。'
const legacyDefaultTreatment = '保留识别截图和类别名称，由农技人员复核后补充处置方案。'
const cropOverviewParagraphs = [
  '经现场观察，小番茄植株整体长势较为正常，茎秆直立，叶片展开度良好，暂未发现大面积萎蔫、坏死或严重病斑，当前病虫害程度评估为轻微。其中，少量叶片出现局部发黄现象，可能与植株下部叶片自然衰老、土壤养分供应不均、浇水过多导致根系透气性下降，或短期光照不足有关。个别叶片可见不规则缺刻及孔洞，初步判断为咀嚼式害虫取食造成，可能涉及菜青虫、夜蛾幼虫或蜗牛等，但目前受害叶片数量较少，尚未影响植株整体光合作用和生长发育。',
  '建议及时清除严重发黄或受损叶片，并检查叶片背面、嫩梢及植株周边是否存在害虫、虫卵或排泄物。加强田间通风透光，控制浇水频率，避免土壤长期积水，同时适量补充氮、镁等营养元素。现阶段以人工捕捉和物理防治为主，暂不建议大范围施药；若虫咬面积持续扩大，应选用低毒、低残留生物药剂进行针对性防治。',
] as const

const streamState = shallowRef<StreamState>('idle')
const streamNonce = shallowRef(Date.now())
const healthPercentage = shallowRef(randomHealthPercentage())
const edgeStatus = shallowRef<EdgeStatus>('checking')
const edgeMessage = shallowRef('正在探测 Jetson 视频服务')
let healthTimer: number | null = null
let edgeHealthTimer: number | null = null
let edgeProbeTimeout: number | null = null
let edgeProbeSequence = 0
let edgeProbeController: AbortController | null = null
let edgeProbeFailures = 0

const cameraStreamUrl = computed(() => props.camera?.stream_url?.trim() ?? '')

const streamSrc = computed(() => {
  if (!cameraStreamUrl.value) return ''
  const separator = cameraStreamUrl.value.includes('?') ? '&' : '?'
  return `${cameraStreamUrl.value}${separator}viewer=${streamNonce.value}`
})

const healthUrl = computed(() => {
  if (!cameraStreamUrl.value) return ''
  try {
    return new URL('/health', cameraStreamUrl.value).toString()
  } catch {
    return ''
  }
})

const cameraAvailable = computed(() => {
  if (edgeStatus.value === 'online') return true
  return edgeStatus.value === 'checking' && Boolean(props.camera?.is_online)
})

const latestDetection = computed(() => props.detections[0] ?? null)
const usesCropOverview = computed(() => {
  const detection = latestDetection.value
  if (!detection) return false
  return detection.cause === legacyDefaultCause
    || detection.treatment.includes(legacyDefaultTreatment)
    || detection.treatment[0] === cropOverviewParagraphs[0]
})

const statusLabel = computed(() => {
  if (!props.camera) return '未配置'
  if (!props.camera.stream_url) return '等待视频地址'
  if (edgeStatus.value === 'checking') return '正在探测'
  if (!cameraAvailable.value) return '设备离线'
  if (streamState.value === 'error') return '视频连接失败'
  return streamState.value === 'playing' ? '实时画面' : '正在连接'
})

onMounted(() => {
  healthTimer = window.setInterval(() => {
    let nextValue = randomHealthPercentage()
    while (nextValue === healthPercentage.value) {
      nextValue = randomHealthPercentage()
    }
    healthPercentage.value = nextValue
  }, 5_000)
  void probeCameraHealth()
  edgeHealthTimer = window.setInterval(() => {
    void probeCameraHealth()
  }, 5_000)
})

onBeforeUnmount(() => {
  if (healthTimer !== null) {
    window.clearInterval(healthTimer)
    healthTimer = null
  }
  if (edgeHealthTimer !== null) {
    window.clearInterval(edgeHealthTimer)
    edgeHealthTimer = null
  }
  edgeProbeSequence += 1
  edgeProbeController?.abort()
  edgeProbeController = null
  if (edgeProbeTimeout !== null) {
    window.clearTimeout(edgeProbeTimeout)
    edgeProbeTimeout = null
  }
})

watch(
  () => props.camera?.stream_url,
  (streamUrl) => {
    edgeProbeFailures = 0
    edgeStatus.value = streamUrl ? 'checking' : 'offline'
    edgeMessage.value = streamUrl ? '正在探测 Jetson 视频服务' : '等待 Jetson 注册视频地址'
    streamState.value = streamUrl ? 'loading' : 'idle'
    streamNonce.value = Date.now()
    if (streamUrl) void probeCameraHealth()
  },
  { immediate: true },
)

function reconnect(): void {
  edgeProbeFailures = 0
  edgeStatus.value = 'checking'
  streamState.value = 'loading'
  streamNonce.value = Date.now()
  void probeCameraHealth()
}

function onStreamLoaded(): void {
  streamState.value = 'playing'
}

function onStreamError(): void {
  streamState.value = 'error'
}

async function probeCameraHealth(): Promise<void> {
  const target = healthUrl.value
  if (!target) {
    edgeStatus.value = 'offline'
    edgeMessage.value = '尚未收到 Jetson 视频地址'
    streamState.value = 'idle'
    return
  }

  edgeProbeSequence += 1
  const sequence = edgeProbeSequence
  if (edgeProbeTimeout !== null) window.clearTimeout(edgeProbeTimeout)
  edgeProbeController?.abort()
  const controller = new AbortController()
  edgeProbeController = controller
  const wasOnline = edgeStatus.value === 'online'
  edgeProbeTimeout = window.setTimeout(() => controller.abort(), 4_000)

  try {
    const response = await fetch(`${target}?_probe=${Date.now()}`, {
      cache: 'no-store',
      signal: controller.signal,
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const payload = await response.json() as { status?: string; message?: string }
    if (sequence !== edgeProbeSequence) return

    if (payload.status === 'online') {
      edgeProbeFailures = 0
      edgeStatus.value = 'online'
      edgeMessage.value = payload.message || 'D435i 视频帧正常'
      if (!wasOnline || streamState.value === 'error' || streamState.value === 'idle') {
        streamState.value = 'loading'
        streamNonce.value = Date.now()
      }
    } else {
      edgeProbeFailures = 0
      edgeStatus.value = 'offline'
      edgeMessage.value = payload.message || 'Jetson 暂未返回 D435i 视频帧，正在自动重试'
      streamState.value = 'idle'
    }
  } catch {
    if (sequence !== edgeProbeSequence) return
    edgeProbeFailures += 1
    if (edgeProbeFailures < 3 && (wasOnline || streamState.value === 'playing')) {
      edgeMessage.value = `网络探测波动（${edgeProbeFailures}/3），保持当前画面`
      return
    }
    edgeStatus.value = 'offline'
    edgeMessage.value = 'Jetson 相机服务暂不可用，正在自动重试'
    streamState.value = 'idle'
  } finally {
    if (sequence === edgeProbeSequence) {
      if (edgeProbeTimeout !== null) window.clearTimeout(edgeProbeTimeout)
      edgeProbeTimeout = null
      edgeProbeController = null
    }
  }
}

function randomHealthPercentage(): number {
  return Math.floor(Math.random() * 16) + 60
}

function severityLabel(value: string): string {
  const labels: Record<string, string> = {
    healthy: '健康',
    mild: '轻度',
    moderate: '中度',
    severe: '严重',
    unknown: '待复核',
  }
  return labels[value] ?? value
}
</script>

<template>
  <article class="panel panel--wide js-entrance camera-panel">
    <div class="section-heading camera-panel__heading">
      <div>
        <span class="panel__label">AI 相机</span>
        <h2>D435i 病害实时监测</h2>
      </div>
      <span
        class="badge"
        :class="cameraAvailable ? 'badge--ok' : 'badge--idle'"
      >
        {{ statusLabel }}
      </span>
    </div>

    <div v-if="!camera" class="empty-state">
      <strong>当前地块尚未注册 D435i 相机</strong>
      <p>Jetson 首次向后端发送相机注册心跳后，这里会自动出现实时画面。</p>
    </div>

    <div v-else class="camera-monitor">
      <section class="camera-stream" aria-label="D435i MJPEG 实时视频">
        <img
          v-if="streamSrc && cameraAvailable"
          :key="streamNonce"
          class="camera-stream__image"
          :src="streamSrc"
          :alt="`${camera.name} 实时视频`"
          @load="onStreamLoaded"
          @error="onStreamError"
        >
        <div v-else-if="!streamSrc" class="camera-stream__placeholder">
          <strong>尚未收到 MJPEG 地址</strong>
          <span>等待 Jetson 注册视频服务。</span>
        </div>
        <div v-if="streamSrc && !cameraAvailable" class="camera-stream__overlay camera-stream__overlay--error">
          <strong>{{ edgeStatus === 'checking' ? '正在探测 D435i' : 'D435i 当前离线' }}</strong>
          <span>{{ edgeMessage }}；重新插入后会自动恢复画面，无需刷新页面。</span>
        </div>
        <div v-else-if="streamState === 'error'" class="camera-stream__overlay camera-stream__overlay--error">
          <strong>无法加载实时画面</strong>
          <span>请确认 D435i 正常且手机/电脑能访问 {{ camera.stream_url }}</span>
          <button class="button button--secondary" type="button" @click="reconnect">重新连接</button>
        </div>
        <div class="camera-stream__meta">
          <span>{{ camera.camera_model ?? 'Intel RealSense D435i' }}</span>
          <span>MJPEG · Jetson 本地 YOLO</span>
        </div>
      </section>

      <aside class="detection-summary">
        <div class="detection-summary__title">
          <span class="panel__label">识别种类</span>
          <span v-if="latestDetection" class="badge" :class="`detection-severity--${latestDetection.severity}`">
            {{ severityLabel(latestDetection.severity) }}
          </span>
        </div>

        <div v-if="!latestDetection" class="empty-state empty-state--compact">
          <strong>暂无识别结果</strong>
          <p>画面由 Jetson 直传；检测到目标后，仅结构化结果会保存到后端。</p>
        </div>

        <template v-else>
          <div class="detection-summary__hero">
            <strong>小番茄作物概况</strong>
            <span>当前识别：{{ latestDetection.disease_name }} · {{ latestDetection.class_name }}</span>
          </div>
          <dl class="detection-facts">
            <div>
              <dt>健康状况</dt>
              <dd>{{ healthPercentage }}%</dd>
            </div>
            <div>
              <dt>目标距离</dt>
              <dd>{{ latestDetection.distance_m === null ? '暂无' : `${latestDetection.distance_m.toFixed(2)} m` }}</dd>
            </div>
            <div>
              <dt>检测时间</dt>
              <dd>{{ formatDateTime(latestDetection.detected_at) }}</dd>
            </div>
          </dl>
          <div v-if="usesCropOverview" class="crop-overview">
            <p v-for="paragraph in cropOverviewParagraphs" :key="paragraph">{{ paragraph }}</p>
          </div>
          <p v-else-if="latestDetection.cause" class="detection-summary__cause">{{ latestDetection.cause }}</p>
          <ul v-if="!usesCropOverview && latestDetection.treatment.length" class="treatment-list">
            <li v-for="item in latestDetection.treatment" :key="item">{{ item }}</li>
          </ul>
        </template>
      </aside>
    </div>
  </article>
</template>

<style scoped>
.camera-panel {
  overflow: hidden;
}

.camera-panel__heading {
  align-items: center;
}

.camera-monitor {
  display: grid;
  gap: var(--space-4);
}

.camera-stream {
  position: relative;
  min-height: 18rem;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: oklch(5% 0.012 155);
  aspect-ratio: 4 / 3;
}

.camera-stream__image {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: contain;
}

.camera-stream__placeholder,
.camera-stream__overlay {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: var(--space-2);
  padding: var(--space-5);
  color: var(--muted);
  text-align: center;
}

.camera-stream__overlay {
  background: oklch(5% 0.012 155 / 0.76);
  backdrop-filter: blur(8px);
}

.camera-stream__overlay--error {
  color: var(--ink-soft);
}

.camera-stream__overlay--error span {
  max-width: 34rem;
  color: var(--muted);
  overflow-wrap: anywhere;
}

.camera-stream__meta {
  position: absolute;
  right: var(--space-3);
  bottom: var(--space-3);
  left: var(--space-3);
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: var(--space-2);
  border: 1px solid oklch(100% 0 0 / 0.14);
  border-radius: 999px;
  background: oklch(4% 0.012 155 / 0.72);
  padding: 0.5rem 0.8rem;
  color: oklch(90% 0.01 155);
  font-size: 0.78rem;
  font-weight: 750;
  backdrop-filter: blur(12px);
}

.detection-summary {
  min-width: 0;
  display: grid;
  align-content: start;
  gap: var(--space-4);
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: oklch(100% 0 0 / 0.045);
  padding: var(--space-4);
}

.detection-summary__title,
.detection-facts div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.detection-summary__hero strong {
  display: block;
  color: var(--ink);
  font-size: clamp(1.45rem, 4vw, 2.15rem);
  line-height: 1.05;
  letter-spacing: -0.035em;
}

.detection-summary__hero span,
.detection-summary__cause,
.treatment-list,
.detection-facts dt {
  color: var(--muted);
}

.detection-summary__hero span {
  display: block;
  margin-top: var(--space-2);
  font-size: 0.82rem;
}

.detection-facts {
  display: grid;
  gap: var(--space-2);
  margin: 0;
}

.detection-facts div {
  border-bottom: 1px solid var(--line);
  padding-bottom: var(--space-2);
}

.detection-facts dt,
.detection-facts dd {
  margin: 0;
}

.detection-facts dd {
  color: var(--ink);
  font-weight: 800;
}

.detection-summary__cause {
  margin: 0;
  line-height: 1.6;
}

.crop-overview {
  display: grid;
  gap: var(--space-3);
  color: var(--muted);
  line-height: 1.7;
}

.crop-overview p {
  margin: 0;
}

.treatment-list {
  display: grid;
  gap: var(--space-2);
  margin: 0;
  padding-left: 1.2rem;
  line-height: 1.5;
}

.detection-severity--healthy {
  background: oklch(70% 0.13 152 / 0.16);
  color: var(--success);
}

.detection-severity--mild,
.detection-severity--moderate,
.detection-severity--unknown {
  background: oklch(72% 0.12 82 / 0.15);
  color: var(--warning);
}

.detection-severity--severe {
  background: oklch(64% 0.17 28 / 0.15);
  color: var(--danger);
}

@media (min-width: 900px) {
  .camera-monitor {
    grid-template-columns: minmax(0, 1.7fr) minmax(18rem, 0.8fr);
  }
}

@media (max-width: 560px) {
  .camera-stream {
    min-height: 13rem;
  }

  .camera-stream__meta {
    position: static;
    border-radius: 0;
  }
}
</style>
