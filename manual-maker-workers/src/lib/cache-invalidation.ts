import { caches } from './memory-cache';

export function invalidateConfig() {
  caches.config.delete('config');
}

export function invalidateI18n(lang?: string) {
  if (lang) {
    caches.i18n.delete(`i18n:${lang}`);
  } else {
    // 全言語クリア（非効率だが頻度低い操作想定）
    caches.i18n.clear();
  }
}

export function invalidatePiiPatterns() {
  caches.piiPatterns.delete('piiPatterns');
}