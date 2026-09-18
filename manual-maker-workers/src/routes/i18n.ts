/**
 * i18n routes - serve translations for the client
 */
import { OpenAPIHono } from '@hono/zod-openapi';
import type { AppEnv } from '../lib/types';
import { z } from 'zod';
import { NotFoundError } from '../lib/errors';
import { 
  ValidationErrorResponseSchema, 
  NotFoundErrorResponseSchema, 
  InternalErrorResponseSchema 
} from '../lib/openapi-errors';
import { caches } from '../lib/memory-cache';
import { openapiI18nDetectBody } from '../lib/openapi-schemas';

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
    result_download_pdf: 'Download PDF (印刷)',
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

export function registerI18nRoutes(app: OpenAPIHono<AppEnv>) {
  app.openapi({
      path: '/api/i18n/languages',
      method: 'get',
      middleware: [],
      summary: 'Get supported languages',
      description: 'Returns list of supported languages and default language',
      responses: {
        '200': {
          description: 'Supported languages',
          content: {
            'application/json': {
              schema: z.object({
                languages: z.array(z.string()),
                default: z.string()
              })
            }
          }
        },
        '400': {
          description: 'Validation error',
          content: {
            'application/json': {
              schema: ValidationErrorResponseSchema
            }
          }
        },
        '500': {
          description: 'Internal server error',
          content: {
            'application/json': {
              schema: InternalErrorResponseSchema
            }
          }
        }
      }
    },
    async (c) => {
      return c.json({ languages: Object.keys(TRANSLATIONS), default: 'ja' });
    }
  );

  app.openapi({
      path: '/api/i18n/translations/{lang}',
      method: 'get',
      middleware: [],
      summary: 'Get translations for a language',
      description: 'Returns translation strings for a specific language',
      request: {
        params: z.object({ lang: z.string() })
      },
      responses: {
        '200': {
          description: 'Translation strings',
          content: {
            'application/json': {
              schema: z.object({
                lang: z.string(),
                translations: z.record(z.string())
              })
            }
          }
        },
        '400': {
          description: 'Validation error',
          content: {
            'application/json': {
              schema: ValidationErrorResponseSchema
            }
          }
        },
        '404': {
          description: 'Unsupported language',
          content: {
            'application/json': {
              schema: NotFoundErrorResponseSchema
            }
          }
        },
        '500': {
          description: 'Internal server error',
          content: {
            'application/json': {
              schema: InternalErrorResponseSchema
            }
          }
        }
      }
    },
     async (c) => {
       const { lang } = c.req.valid('param');
       // Try to get from cache
       const cached = caches.i18n.get(lang);
       if (cached !== undefined) {
         return c.json({ lang, translations: cached });
       }
       const translations = TRANSLATIONS[lang];
       if (!translations) {
         throw new NotFoundError(`Language: ${lang}`);
       }
       // Save to cache
       caches.i18n.set(lang, translations);
       return c.json({ lang, translations });
     }
  );

app.openapi({
       path: '/api/i18n/detect',
       method: 'post',

       summary: 'Detect language from text',
       description: 'Detects language from input text using simple heuristic',
       request: {
          body: {
            required: true,
content: {
              'application/json': {
                 schema: openapiI18nDetectBody
              }
            }
         }
       },
       responses: {
         '200': {
           description: 'Language detection result',
           content: {
             'application/json': {
               schema: z.object({
                 detected: z.enum(['ja', 'en']),
                 confidence: z.number().min(0).max(1)
               })
             }
           }
         },
         '400': {
           description: 'Validation error',
           content: {
             'application/json': {
               schema: ValidationErrorResponseSchema
             }
           }
         },
         '500': {
           description: 'Internal server error',
           content: {
             'application/json': {
               schema: InternalErrorResponseSchema
             }
           }
         }
       }
     },
     async (c) => {
        const body = c.req.valid('json');
       const text = body.text;

       // Simple heuristic: count Japanese characters
       const japaneseChars = (text.match(/[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]/g) || []).length;
       const totalChars = text.length || 1;
       const ratio = japaneseChars / totalChars;

       return c.json({
         detected: ratio > 0.1 ? 'ja' as const : 'en' as const,
         confidence: Math.min(1, ratio * 5)
       });
     }
   );
}