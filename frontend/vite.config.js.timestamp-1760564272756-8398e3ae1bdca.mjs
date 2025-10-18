// vite.config.js
import { defineConfig } from "file:///D:/Projects/repos/storyline-app/frontend/node_modules/vite/dist/node/index.js";
import vue from "file:///D:/Projects/repos/storyline-app/frontend/node_modules/@vitejs/plugin-vue/dist/index.mjs";
import ui from "file:///D:/Projects/repos/storyline-app/frontend/node_modules/@nuxt/ui/dist/vite.mjs";
var vite_config_default = defineConfig({
  plugins: [
    vue(),
    ui({
      ui: {
        colors: {
          primary: "indigo",
          neutral: "slate"
        },
        chatMessage: {
          slots: {
            content: "whitespace-pre-wrap break-words"
          }
        },
        pageGrid: {
          base: "relative grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4"
        }
      }
    })
  ],
  resolve: {
    alias: {
      "@": "/src"
    }
  },
  server: {
    port: 3e3,
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000"
    }
  },
  build: {
    outDir: "../static",
    assetsDir: "assets",
    emptyOutDir: true
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcuanMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCJEOlxcXFxQcm9qZWN0c1xcXFxyZXBvc1xcXFxzdG9yeWxpbmUtYXBwXFxcXGZyb250ZW5kXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ZpbGVuYW1lID0gXCJEOlxcXFxQcm9qZWN0c1xcXFxyZXBvc1xcXFxzdG9yeWxpbmUtYXBwXFxcXGZyb250ZW5kXFxcXHZpdGUuY29uZmlnLmpzXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ltcG9ydF9tZXRhX3VybCA9IFwiZmlsZTovLy9EOi9Qcm9qZWN0cy9yZXBvcy9zdG9yeWxpbmUtYXBwL2Zyb250ZW5kL3ZpdGUuY29uZmlnLmpzXCI7aW1wb3J0IHsgZGVmaW5lQ29uZmlnIH0gZnJvbSAndml0ZSdcbmltcG9ydCB2dWUgZnJvbSAnQHZpdGVqcy9wbHVnaW4tdnVlJ1xuaW1wb3J0IHVpIGZyb20gJ0BudXh0L3VpL3ZpdGUnXG5cbmV4cG9ydCBkZWZhdWx0IGRlZmluZUNvbmZpZyh7XG4gIHBsdWdpbnM6IFtcbiAgICB2dWUoKSxcbiAgICB1aSh7XG4gICAgICB1aToge1xuICAgICAgICBjb2xvcnM6IHtcbiAgICAgICAgICBwcmltYXJ5OiAnaW5kaWdvJyxcbiAgICAgICAgICBuZXV0cmFsOiAnc2xhdGUnXG4gICAgICAgIH0sXG4gICAgICAgIGNoYXRNZXNzYWdlOiB7XG4gICAgICAgICAgc2xvdHM6IHtcbiAgICAgICAgICAgIGNvbnRlbnQ6ICd3aGl0ZXNwYWNlLXByZS13cmFwIGJyZWFrLXdvcmRzJyxcbiAgICAgICAgICB9XG4gICAgICAgIH0sXG4gICAgICAgIHBhZ2VHcmlkOiB7XG4gICAgICAgICAgYmFzZTogJ3JlbGF0aXZlIGdyaWQgZ3JpZC1jb2xzLTIgc206Z3JpZC1jb2xzLTMgbGc6Z3JpZC1jb2xzLTQgeGw6Z3JpZC1jb2xzLTUgZ2FwLTQnXG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9KVxuICBdLFxuICByZXNvbHZlOiB7XG4gICAgYWxpYXM6IHtcbiAgICAgICdAJzogJy9zcmMnXG4gICAgfVxuICB9LFxuICBzZXJ2ZXI6IHtcbiAgICBwb3J0OiAzMDAwLFxuICAgIHByb3h5OiB7XG4gICAgICAnL2FwaSc6ICdodHRwOi8vbG9jYWxob3N0OjgwMDAnLFxuICAgICAgJy9oZWFsdGgnOiAnaHR0cDovL2xvY2FsaG9zdDo4MDAwJ1xuICAgIH1cbiAgfSxcbiAgYnVpbGQ6IHtcbiAgICBvdXREaXI6ICcuLi9zdGF0aWMnLFxuICAgIGFzc2V0c0RpcjogJ2Fzc2V0cycsXG4gICAgZW1wdHlPdXREaXI6IHRydWUsXG4gIH1cbn0pIl0sCiAgIm1hcHBpbmdzIjogIjtBQUFvVCxTQUFTLG9CQUFvQjtBQUNqVixPQUFPLFNBQVM7QUFDaEIsT0FBTyxRQUFRO0FBRWYsSUFBTyxzQkFBUSxhQUFhO0FBQUEsRUFDMUIsU0FBUztBQUFBLElBQ1AsSUFBSTtBQUFBLElBQ0osR0FBRztBQUFBLE1BQ0QsSUFBSTtBQUFBLFFBQ0YsUUFBUTtBQUFBLFVBQ04sU0FBUztBQUFBLFVBQ1QsU0FBUztBQUFBLFFBQ1g7QUFBQSxRQUNBLGFBQWE7QUFBQSxVQUNYLE9BQU87QUFBQSxZQUNMLFNBQVM7QUFBQSxVQUNYO0FBQUEsUUFDRjtBQUFBLFFBQ0EsVUFBVTtBQUFBLFVBQ1IsTUFBTTtBQUFBLFFBQ1I7QUFBQSxNQUNGO0FBQUEsSUFDRixDQUFDO0FBQUEsRUFDSDtBQUFBLEVBQ0EsU0FBUztBQUFBLElBQ1AsT0FBTztBQUFBLE1BQ0wsS0FBSztBQUFBLElBQ1A7QUFBQSxFQUNGO0FBQUEsRUFDQSxRQUFRO0FBQUEsSUFDTixNQUFNO0FBQUEsSUFDTixPQUFPO0FBQUEsTUFDTCxRQUFRO0FBQUEsTUFDUixXQUFXO0FBQUEsSUFDYjtBQUFBLEVBQ0Y7QUFBQSxFQUNBLE9BQU87QUFBQSxJQUNMLFFBQVE7QUFBQSxJQUNSLFdBQVc7QUFBQSxJQUNYLGFBQWE7QUFBQSxFQUNmO0FBQ0YsQ0FBQzsiLAogICJuYW1lcyI6IFtdCn0K
