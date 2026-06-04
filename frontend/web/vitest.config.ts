import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { existsSync, readdirSync } from 'node:fs';

const root = path.resolve(__dirname);
console.log('[vitest-debug] __dirname:', __dirname);
console.log('[vitest-debug] root:', root);
console.log('[vitest-debug] lib/api.ts exists:', existsSync(path.join(root, 'lib', 'api.ts')));
console.log('[vitest-debug] lib/ contents:', readdirSync(path.join(root, 'lib')));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': root,
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./__tests__/setup.ts'],
    globals: true,
  },
});
