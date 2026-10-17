import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backend = env.VITE_API_BASE_URL || 'http://172.20.10.2:8000'

  return {
    plugins: [vue()],
    resolve: { alias: { '@': '/src' } },
    server: {
      port: 9528,
      proxy: {
        '/api': { target: backend, changeOrigin: true },
        '/ws': { target: backend.replace(/^http/, 'ws'), ws: true, changeOrigin: true },
      },
    },
    preview: { port: 9529 },
    build: { target: 'es2022', outDir: 'dist', sourcemap: false },
  }
})
