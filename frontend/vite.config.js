import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': '/src'
    }
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/characters': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/sessions': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/interact': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: '../static',
    assetsDir: 'assets',
    emptyOutDir: true,
  }
})