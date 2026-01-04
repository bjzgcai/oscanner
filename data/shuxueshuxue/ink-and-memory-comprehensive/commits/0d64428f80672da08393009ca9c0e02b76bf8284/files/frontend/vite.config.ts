import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/ink-and-memory/',  // Deploy at lexicalmathical.com/ink-and-memory/
})
