import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: { preserveSymlinks: true },
  server: {
    host: 'localhost', port: 5173, strictPort: true,
    proxy: { '/api': { target: (globalThis as { process?: { env: Record<string, string | undefined> } }).process?.env.ORBITRA_API_PROXY_TARGET || 'http://127.0.0.1:8000', ws: true, changeOrigin: false } },
  },
})
