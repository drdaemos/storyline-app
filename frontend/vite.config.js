import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import ui from '@nuxt/ui/vite'

export default defineConfig({
  plugins: [
    vue(),
    ui({
      ui: {
        colors: {
          primary: 'indigo',
          neutral: 'slate'
        },
        chatMessage: {
          slots: {
            content: 'whitespace-pre-wrap break-words',
          }
        },
        pageGrid: {
          base: 'relative grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4'
        }
      }
    })
  ],
  resolve: {
    alias: {
      '@': '/src'
    }
  },
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000'
    }
  },
  build: {
    outDir: '../static',
    assetsDir: 'assets',
    emptyOutDir: true,
  }
})