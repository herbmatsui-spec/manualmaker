import '@hono/zod-openapi'
import { fileIdParam, paginationQuery, uploadBody, processStartBody, progressUpdateBody, resultSaveBody, geminiProxyParams, geminiProxyBody, visionProxyBody, mermaidSaveBody, piiMaskBody, i18nDetectBody, configQuery } from './schemas'

// OpenAPI-enhanced schemas with descriptions and examples
export const openapiFileIdParam = fileIdParam.openapi({
  description: 'Unique file identifier (UUID or 32-character hex)',
  example: { fileId: '550e8400-e29b-41d4-a716-446655440000' }
})

export const openapiPaginationQuery = paginationQuery.openapi({
  description: 'Pagination parameters',
  example: {
    limit: 20,
    offset: 0
  }
})

export const openapiUploadBody = uploadBody.openapi({
  description: 'File upload request (PDF only)'
})

export const openapiProcessStartBody = processStartBody.openapi({
  description: 'Processing options',
  example: {
    options: {
      compactLayout: true,
      useEmojis: false,
      promptLayout: 'default',
      promptStrictMode: true,
      promptHasDiagrams: false,
      promptLowQualityMode: false,
      baseUrl: 'https://example.com'
    }
  }
})

export const openapiProgressUpdateBody = progressUpdateBody.openapi({
  description: 'Progress update during processing',
  example: {
    progress: 75,
    stage: 'OCR解析中',
    status: 'processing'
  }
})

export const openapiResultSaveBody = resultSaveBody.openapi({
  description: 'Processing result to save',
  example: {
    markdown: '# Sample Manual\n\nThis is a sample manual content.',
    title: 'Sample Manual'
  }
})

export const openapiGeminiProxyParams = geminiProxyParams.openapi({
  description: 'Gemini API proxy parameters',
  example: {
    model: 'gemini-1.5-flash',
    method: 'generateContent'
  }
})

export const openapiGeminiProxyBody = geminiProxyBody.openapi({
  description: 'Gemini API request body',
  example: {
    contents: [{
      parts: [{ text: 'Explain quantum computing' }]
    }]
  }
})

export const openapiVisionProxyBody = visionProxyBody.openapi({
  description: 'Vision API request body',
  example: {
    requests: [{
      image: {
        content: 'base64encodedimagecontent'
      },
      features: [{
        type: 'TEXT_DETECTION',
        maxResults: 10
      }]
    }]
  }
})

export const openapiMermaidSaveBody = mermaidSaveBody.openapi({
  description: 'Mermaid diagram to save',
  example: {
    mermaid: 'graph TD\n    A[Start] --> B{Decision}\n    B -->|Yes| C[OK]\n    B -->|No| D[Error]'
  }
})

export const openapiPiiMaskBody = piiMaskBody.openapi({
  description: 'Text to mask for PII',
  example: {
    text: 'Contact John Doe at john@example.com or 555-123-4567'
  }
})

export const openapiI18nDetectBody = i18nDetectBody.openapi({
  description: 'Text for language detection',
  example: {
    text: 'これは日本語のテキストです。'
  }
})

export const openapiConfigQuery = configQuery.openapi({
  description: 'Configuration query (no parameters)',
  example: {}
})

