import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/health': 'http://localhost:2048',
      '/events': 'http://localhost:2048',
      '/runs': 'http://localhost:2048',
      '/graph': 'http://localhost:2048',
      '/logs': 'http://localhost:2048',
      '/errors': 'http://localhost:2048',
      '/nodes': 'http://localhost:2048',
      '/stream': {
        target: 'http://localhost:2048',
        ws: true,
        changeOrigin: true,
      },
    },
  },
})
