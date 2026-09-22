import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { readFileSync } from 'node:fs'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), {
    name: 'buddha-shared-site-assets',
    configureServer(server) {
      // These same files are served from frontend/ by Nginx and reader_app.
      const assets: Record<string, string> = {
        '/css/site-header.css': 'text/css',
        '/assets/buddha-line.png': 'image/png',
        '/assets/favicon.ico': 'image/x-icon',
      };
      server.middlewares.use((request, response, next) => {
        const pathname = request.url?.split('?')[0] || '';
        if (!Object.hasOwn(assets, pathname)) return next();
        response.setHeader('Content-Type', assets[pathname]);
        response.end(readFileSync(path.resolve(__dirname, '..', pathname.slice(1))));
      });
    },
  }],
  base: '/pali/',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
