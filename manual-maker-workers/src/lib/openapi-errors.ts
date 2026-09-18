import { z } from 'zod';

export const ErrorResponseSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    requestId: z.string(),
    details: z.unknown().optional(),
  }),
});

export type ErrorResponse = z.infer<typeof ErrorResponseSchema>;

// Specific error response schemas for common error types (optional)
export const ValidationErrorResponseSchema = ErrorResponseSchema.extend({
  error: z.object({
    code: z.literal('VALIDATION_ERROR'),
    message: z.string(),
    requestId: z.string(),
    details: z.unknown().optional(),
  }),
});

export const NotFoundErrorResponseSchema = ErrorResponseSchema.extend({
  error: z.object({
    code: z.literal('NOT_FOUND'),
    message: z.string(),
    requestId: z.string(),
    details: z.unknown().optional(),
  }),
});

export const ExternalAPIErrorResponseSchema = ErrorResponseSchema.extend({
  error: z.object({
    code: z.literal('EXTERNAL_API_ERROR'),
    message: z.string(),
    requestId: z.string(),
    details: z.unknown().optional(),
  }),
});

export const StorageErrorResponseSchema = ErrorResponseSchema.extend({
  error: z.object({
    code: z.literal('STORAGE_ERROR'),
    message: z.string(),
    requestId: z.string(),
    details: z.unknown().optional(),
  }),
});

export const RateLimitErrorResponseSchema = ErrorResponseSchema.extend({
  error: z.object({
    code: z.literal('RATE_LIMIT_EXCEEDED'),
    message: z.literal('Too many requests'),
    requestId: z.string(),
    details: z.object({ retryAfter: z.number() }).optional(),
  }),
});

export const InternalErrorResponseSchema = ErrorResponseSchema.extend({
  error: z.object({
    code: z.literal('INTERNAL_ERROR'),
    message: z.literal('Internal server error'),
    requestId: z.string(),
    details: z.unknown().optional(),
  }),
});