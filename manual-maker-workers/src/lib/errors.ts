export class AppError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly statusCode: number = 500,
    public readonly details?: unknown
  ) {
    super(message);
    this.name = 'AppError';
  }
}

export class ValidationError extends AppError {
  constructor(message: string, details?: unknown) {
    super('VALIDATION_ERROR', message, 400, details);
    this.name = 'ValidationError';
  }
}

export class StorageError extends AppError {
  constructor(message: string, details?: unknown) {
    super('STORAGE_ERROR', message, 500, details);
    this.name = 'StorageError';
  }
}

export class ExternalAPIError extends AppError {
  constructor(
    public readonly service: 'gemini' | 'vision',
    message: string,
    public readonly upstreamStatus?: number,
    details?: unknown
  ) {
    super('EXTERNAL_API_ERROR', message, upstreamStatus === 429 ? 429 : 502, details);
    this.name = 'ExternalAPIError';
  }
}

export class RateLimitError extends AppError {
  constructor(retryAfter: number) {
    super('RATE_LIMIT_EXCEEDED', 'Too many requests', 429, { retryAfter });
    this.name = 'RateLimitError';
  }
}

export class NotFoundError extends AppError {
  constructor(resource: string) {
    super('NOT_FOUND', `${resource} not found`, 404);
    this.name = 'NotFoundError';
  }
}