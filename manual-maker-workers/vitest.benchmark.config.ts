import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['benchmark/**/*.test.ts'],
    fileParallelism: false,
    maxWorkers: 1,
  },
});
