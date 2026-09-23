import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Read VITE_* from the project's single root .env; only VITE_-prefixed
  // keys are ever exposed to the browser bundle.
  envDir: '..',
  server: {
    port: 5173,
    open: false
  }
})
