import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: '/admin/',
  plugins: [vue(), tailwindcss()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
  build: {
    rollupOptions: {
      input: { main: 'index.html', sub: 'sub.html' },
      output: {
        entryFileNames: 'assets/[name].js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name][extname]',
      },
    },
  },
})
