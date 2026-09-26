import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

// Backend FastAPI (python -m src.api_server) chạy ở cổng 8000; Vite proxy /api sang đó.
const API_TARGET = process.env.RAG_API_URL || 'http://127.0.0.1:8000';

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(import.meta.dirname, '.'),
      },
    },
    server: {
      proxy: {
        '/api': {target: API_TARGET, changeOrigin: true},
      },
    },
  };
});
