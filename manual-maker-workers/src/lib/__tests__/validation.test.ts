import { describe, it, expect } from 'vitest';
import { Hono } from 'hono';
import { z } from 'zod';
import { validate, getValidatedBody, getValidatedParams } from '../validation';
import { ValidationError } from '../errors';
import { bodyLimit } from '../body-limit';
import { fileIdParam, uploadBody, processStartBody, progressUpdateBody, resultSaveBody } from '../schemas';

function validationApp(schemas: { body?: z.ZodSchema; params?: z.ZodSchema; query?: z.ZodSchema }) {
  const app = new Hono();
  app.onError((error, c) => {
    if (error instanceof ValidationError) return c.json({ error: error.code }, 400);
    return c.json({ error: 'unexpected' }, 500);
  });
  app.post('/', validate(schemas), c => 
    c.json({ 
      body: getValidatedBody<unknown>(c),
      params: getValidatedParams<unknown>(c)
    }));
  return app;
}

function validationAppWithParams(schemas: { params: z.ZodSchema }) {
  const app = new Hono();
  app.onError((error, c) => {
    if (error instanceof ValidationError) return c.json({ error: error.code }, 400);
    return c.json({ error: 'unexpected' }, 500);
  });
  app.get('/:id', validate(schemas), c => 
    c.json({ params: getValidatedParams<unknown>(c) }));
  return app;
}

describe('Validation Middleware', () => {
  it('should validate JSON body correctly', async () => {
    const response = await validationApp({ body: z.object({ name: z.string() }) }).request('/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'test' }),
    });
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ 
      body: { name: 'test' },
      params: undefined
    });
  });

  it('should reject invalid body', async () => {
    const response = await validationApp({ body: z.object({ name: z.string() }) }).request('/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
    });
    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ error: 'VALIDATION_ERROR' });
  });

  it('should validate params correctly', async () => {
    const response = await validationAppWithParams({ params: z.object({ id: z.string() }) }).request('/test123', {
      method: 'GET',
    });
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ 
      params: { id: 'test123' },
      body: undefined
    });
  });

  it('should reject invalid params', async () => {
    const response = await validationAppWithParams({ params: z.object({ id: z.number() }) }).request('/invalid', {
      method: 'GET',
    });
    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ error: 'VALIDATION_ERROR' });
  });
});

describe('Schema Definitions - Valid Data', () => {
  it('fileIdParam should validate UUID', () => {
    expect(fileIdParam.safeParse({ fileId: '550e8400-e29b-41d4-a716-446655440000' }).success).toBe(true);
  });
  it('fileIdParam should validate 32-char hex', () => {
    expect(fileIdParam.safeParse({ fileId: 'a'.repeat(32) }).success).toBe(true);
  });
  it('uploadBody should accept File with PDF type', () => {
    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' });
    expect(uploadBody.safeParse({ file }).success).toBe(true);
  });
  it('processStartBody should accept valid options', () => {
    expect(processStartBody.safeParse({ 
      options: {
        compactLayout: true,
        useEmojis: false,
        promptLayout: 'default',
        promptStrictMode: true,
        promptHasDiagrams: false,
        promptLowQualityMode: false,
        baseUrl: 'https://example.com'
      }
    }).success).toBe(true);
  });
  it('progressUpdateBody should accept valid progress update', () => {
    expect(progressUpdateBody.safeParse({ 
      progress: 75,
      stage: 'OCR解析中',
      status: 'processing'
    }).success).toBe(true);
  });
  it('resultSaveBody should accept valid result', () => {
    expect(resultSaveBody.safeParse({ 
      markdown: '# Test\n\nThis is a test.',
      title: 'Test Document'
    }).success).toBe(true);
  });
});

describe('Schema Definitions - Invalid Data', () => {
  it.each([
    '123e4567-e89b-12d3-a456-426614174000',
    'invalid-file-id',
    'g'.repeat(33),
    '',
    'file..pdf'
  ])('fileIdParam should reject invalid ID %s', fileId => {
    expect(fileIdParam.safeParse({ fileId }).success).toBe(false);
  });

  it('uploadBody should reject non-PDF file', () => {
    const file = new File(['test'], 'test.txt', { type: 'text/plain' });
    expect(uploadBody.safeParse({ file }).success).toBe(false);
  });

  it('uploadBody should reject non-File value', () => {
    expect(uploadBody.safeParse({ file: 'not-a-file' }).success).toBe(false);
  });

  it('processStartBody should reject missing options', () => {
    expect(processStartBody.safeParse({}).success).toBe(false);
  });

  it('processStartBody should reject invalid options type', () => {
    expect(processStartBody.safeParse({ options: 'invalid' }).success).toBe(false);
  });

  it('progressUpdateBody should reject progress out of range (< 0)', () => {
    expect(progressUpdateBody.safeParse({ progress: -1 }).success).toBe(false);
  });

  it('progressUpdateBody should reject progress out of range (> 100)', () => {
    expect(progressUpdateBody.safeParse({ progress: 101 }).success).toBe(false);
  });

  it('progressUpdateBody should reject non-numeric progress', () => {
    expect(progressUpdateBody.safeParse({ progress: 'invalid' }).success).toBe(false);
  });

  it('resultSaveBody should reject empty markdown', () => {
    expect(resultSaveBody.safeParse({ markdown: '' }).success).toBe(false);
  });

  it('resultSaveBody should reject non-string markdown', () => {
    expect(resultSaveBody.safeParse({ markdown: 123 }).success).toBe(false);
  });
});

describe('FormData Support Test', () => {
  it('should validate File in FormData correctly', async () => {
    const app = new Hono();
    app.onError((error, c) => {
      if (error instanceof ValidationError) return c.json({ error: error.code }, 400);
      return c.json({ error: 'unexpected' }, 500);
    });
    app.post('/upload', validate({ 
      body: z.object({
        file: z.instanceof(File).refine(f => f.type === 'application/pdf', 'Only PDF allowed')
      })
    }), async (c) => {
      const body = getValidatedBody<{ file: File }>(c);
      return c.json({ 
        filename: body.file.name,
        type: body.file.type 
      });
    });

    // Create a FormData with a file
    const formData = new FormData();
    const file = new File(['test content'], 'test.pdf', { type: 'application/pdf' });
    formData.append('file', file);

    const response = await app.request('/upload', {
      method: 'POST',
      body: formData,
    });

    expect(response.status).toBe(200);
    const json = await response.json();
    expect(json.filename).toBe('test.pdf');
    expect(json.type).toBe('application/pdf');
  });

  it('should reject invalid file type in FormData', async () => {
    const app = new Hono();
    app.onError((error, c) => {
      if (error instanceof ValidationError) return c.json({ error: error.code }, 400);
      return c.json({ error: 'unexpected' }, 500);
    });
    app.post('/upload', validate({ 
      body: z.object({
        file: z.instanceof(File).refine(f => f.type === 'application/pdf', 'Only PDF allowed')
      })
    }), async (c) => {
      const body = getValidatedBody<{ file: File }>(c);
      return c.json({ 
        filename: body.file.name,
        type: body.file.type 
      });
    });

    // Create a FormData with a non-PDF file
    const formData = new FormData();
    const file = new File(['test content'], 'test.txt', { type: 'text/plain' });
    formData.append('file', file);

    const response = await app.request('/upload', {
      method: 'POST',
      body: formData,
    });

    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ error: 'VALIDATION_ERROR' });
  });
});

describe('Body Limit Middleware', () => {
  function app() {
    const app = new Hono();
    app.post('/', bodyLimit({ maxSize: 1024 }), c => c.text('accepted'));
    return app;
  }
  it('should allow requests under limit', async () => {
    const response = await app().request('/', {
      method: 'POST', headers: { 'Content-Length': '512' }, body: 'x'.repeat(512),
    });
    expect(response.status).toBe(200);
    expect(await response.text()).toBe('accepted');
  });
  it('should reject requests over limit', async () => {
    const response = await app().request('/', {
      method: 'POST', headers: { 'Content-Length': '2048' }, body: 'x'.repeat(2048),
    });
    expect(response.status).toBe(413);
    expect(await response.json()).toEqual({ error: 'Request body too large', maxSize: 1024 });
  });
});