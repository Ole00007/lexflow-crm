import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base: './' so the built bundle works from any path — static hosting on
// Cloudflare Workers (Assets), Cloudflare Pages, or a Railway static server.
export default defineConfig({
  plugins: [react()],
  base: './',
  server: { port: 5180, strictPort: true },
  preview: { port: 5180, strictPort: true },
})
