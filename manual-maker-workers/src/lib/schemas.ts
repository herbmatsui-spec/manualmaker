import { z } from '@hono/zod-openapi';

// 共通パラメータ
export const fileIdParam = z.object({
  fileId: z.string().regex(
    /^[a-f0-9]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i, 
    'Invalid fileId format'
  ).openapi({
    description: 'File identifier (UUID or 32-character hex)',
    example: '550e8400-e29b-41d4-a716-446655440000'
  })
});

export const paginationQuery = z.object({
  limit: z.coerce.number().int().min(1).max(100).default(20).openapi({
    description: 'Number of items to return per page',
    example: 20
  }),
  offset: z.coerce.number().int().min(0).default(0).openapi({
    description: 'Number of items to skip',
    example: 0
  })
});

// アップロード
export const uploadBody = z.object({
  file: z.instanceof(File).refine(f => f.type === 'application/pdf', 'Only PDF allowed')
}).openapi({
  description: 'PDF file to upload',
  // FileオブジェクトはJSONシリアライズできないため、説明のみ
}).passthrough(); // FormData対応

// 処理開始
export const processStartBody = z.object({
  options: z.object({
    compactLayout: z.boolean().optional().openapi({
      description: 'Use compact layout for output',
      example: false
    }),
    useEmojis: z.boolean().optional().openapi({
      description: 'Use emojis in output',
      example: true
    }),
    promptLayout: z.string().optional().openapi({
      description: 'Layout prompt for processing',
      example: 'detailed'
    }),
    promptStrictMode: z.boolean().optional().openapi({
      description: 'Enable strict prompt mode',
      example: false
    }),
    promptHasDiagrams: z.boolean().optional().openapi({
      description: 'Input contains diagrams',
      example: true
    }),
    promptLowQualityMode: z.boolean().optional().openapi({
      description: 'Enable low quality mode',
      example: false
    }),
    baseUrl: z.string().url().optional().openapi({
      description: 'Base URL for relative links',
      example: 'https://example.com'
    })
  }).openapi({
    description: 'Processing options'
  })
}).openapi({
  description: 'Processing start request'
});

// 進捗更新
export const progressUpdateBody = z.object({
  progress: z.number().int().min(0).max(100).openapi({
    description: 'Progress percentage (0-100)',
    example: 75
  }),
  stage: z.string().max(200).optional().openapi({
    description: 'Current processing stage',
    example: 'OCR解析中'
  }),
  status: z.enum(['pending', 'processing', 'completed', 'failed']).optional().openapi({
    description: 'Processing status',
    example: 'processing'
  }),
  result: z.object({
    markdown: z.string().optional().openapi({
      description: 'Generated markdown content',
      example: '# タイトル\n\nこれはサンプルです。'
    }),
    html: z.string().optional().openapi({
      description: 'Generated HTML content',
      example: '<h1>タイトル</h1><p>これはサンプルです。</p>'
    })
  }).optional().openapi({
    description: 'Processing result (when completed)'
  }),
  error: z.string().optional().openapi({
    description: 'Error message (when failed)',
    example: 'Failed to process PDF'
  })
}).openapi({
  description: 'Progress update request'
});

// 結果保存
export const resultSaveBody = z.object({
  markdown: z.string().min(1).max(10 * 1024 * 1024).openapi({
    description: 'Markdown content to save',
    example: '# サンプルマニュアル\n\nこれはサンプルです。'
  }),
  title: z.string().max(300).optional().openapi({
    description: 'Title of the document',
    example: 'サンプルマニュアル'
  })
}).openapi({
  description: 'Result save request'
});

// Geminiプロキシ
export const geminiProxyParams = z.object({
  model: z.string().regex(/^[a-z0-9.\-]+$/i, 'Invalid model name').openapi({
    description: 'Gemini model name',
    example: 'gemini-1.5-flash'
  }),
  method: z.enum(['generateContent', 'streamGenerateContent', 'countTokens']).openapi({
    description: 'Gemini API method to call',
    example: 'generateContent'
  })
}).openapi({
  description: 'Gemini API endpoint parameters'
});

export const geminiProxyBody = z.record(z.unknown()).openapi({
  description: 'Request body to forward to Gemini API',
  // 実際の構造は複雑なので説明のみ
});

// Visionプロキシ
export const visionProxyBody = z.object({
  requests: z.array(z.object({
    image: z.object({ content: z.string() }),
    features: z.array(z.object({ 
      type: z.string(), 
      maxResults: z.number().optional() 
    }))
  })).max(16).openapi({
    description: 'Vision API requests (max 16)',
    example: [{
      image: { content: 'base64encodedimage...' },
      features: [{ type: 'TEXT_DETECTION', maxResults: 100 }]
    }]
  })
}).openapi({
  description: 'Vision API request body'
});

// Mermaid保存
export const mermaidSaveBody = z.object({
  mermaid: z.string().min(1).max(512 * 1024).openapi({
    description: 'Mermaid diagram source',
    example: 'graph TD\n    A[Start] --> B{Decision}\n    B -->|Yes| C[OK]\n    B -->|No| D[Error]'
  })
}).openapi({
  description: 'Mermaid save request'
});

// PIIマスク
export const piiMaskBody = z.object({
  text: z.string().max(1024 * 1024).openapi({
    description: 'Text to mask PII from',
    example: 'Contact me at john@example.com or 555-123-4567'
  })
}).openapi({
  description: 'PII mask request'
});

// i18n言語検出
export const i18nDetectBody = z.object({
  text: z.string().openapi({
    description: 'Text to detect language from',
    example: 'これはサンプルテキストです。'
  })
}).openapi({
  description: 'Language detection request'
});

// 設定取得（クエリパラメータなし）
export const configQuery = z.object({}).openapi({
  description: 'Get application configuration'
});