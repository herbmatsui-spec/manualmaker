/**
 * i18n routes - serve translations for the client
 */
import { Hono } from 'hono';
import type { Env } from '../lib/types';

const TRANSLATIONS: Record<string, Record<string, string>> = {
  ja: {
    app_title: '手書きマニュアル処理システム',
    upload_title: 'PDFをアップロード',
    upload_button: 'アップロード',
    upload_drag: 'ドラッグ＆ドロップ または クリックしてファイルを選択',
    processing: '処理中...',
    progress_stage_extract: 'テキスト抽出中',
    progress_stage_ocr: 'OCR解析中',
    progress_stage_summarize: '要約・構造化中',
    progress_stage_generate: 'マニュアル生成中',
    progress_stage_complete: '完了',
    result_title: '処理結果',
    result_download_md: 'Markdown ダウンロード',
    result_download_pdf: 'PDF ダウンロード (印刷)',
    result_copy: 'クリップボードにコピー',
    mermaid_title: 'フローチャート',
    mermaid_edit: '編集',
    mermaid_render: '再描画',
    error_upload: 'アップロードに失敗しました',
    error_process: '処理に失敗しました',
    error_not_found: 'ファイルが見つかりません',
    language_label: '言語'
  },
  en: {
    app_title: 'Handwritten Manual Processing System',
    upload_title: 'Upload PDF',
    upload_button: 'Upload',
    upload_drag: 'Drag & drop or click to select a file',
    processing: 'Processing...',
    progress_stage_extract: 'Extracting text',
    progress_stage_ocr: 'Running OCR',
    progress_stage_summarize: 'Summarizing & structuring',
    progress_stage_generate: 'Generating manual',
    progress_stage_complete: 'Complete',
    result_title: 'Result',
    result_download_md: 'Download Markdown',
    result_download_pdf: 'Download PDF (Print)',
    result_copy: 'Copy to clipboard',
    mermaid_title: 'Flowchart',
    mermaid_edit: 'Edit',
    mermaid_render: 'Re-render',
    error_upload: 'Upload failed',
    error_process: 'Processing failed',
    error_not_found: 'File not found',
    language_label: 'Language'
  }
};

export function registerI18nRoutes(app: Hono<{ Bindings: Env }>) {
  app.get('/api/i18n/languages', (c) => {
    return c.json({ languages: Object.keys(TRANSLATIONS), default: 'ja' });
  });

  app.get('/api/i18n/translations/:lang', (c) => {
    const lang = c.req.param('lang');
    const translations = TRANSLATIONS[lang];
    if (!translations) {
      return c.json({ error: `Unsupported language: ${lang}` }, 404);
    }
    return c.json({ lang, translations });
  });

  app.post('/api/i18n/detect', async (c) => {
    const body = await c.req.json().catch(() => ({}));
    const text = typeof body.text === 'string' ? body.text : '';

    // Simple heuristic: count Japanese characters
    const japaneseChars = (text.match(/[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]/g) || []).length;
    const totalChars = text.length || 1;
    const ratio = japaneseChars / totalChars;

    return c.json({
      detected: ratio > 0.1 ? 'ja' : 'en',
      confidence: Math.min(1, ratio * 5)
    });
  });
}
