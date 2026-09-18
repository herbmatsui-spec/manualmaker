import { Context, Next } from 'hono';
import { z, ZodSchema, ZodError } from 'zod';
import { ValidationError } from './errors';

type SchemaMap = {
  body?: ZodSchema;
  params?: ZodSchema;
  query?: ZodSchema;
};

export function validate(schemas: SchemaMap) {
  return async (c: Context, next: Next) => {
    try {
      if (schemas.body) {
        const contentType = c.req.header('content-type') || '';
        let body: unknown;
        if (contentType.includes('multipart/form-data')) {
          body = await c.req.parseBody();
        } else if (contentType.includes('application/json')) {
          body = await c.req.json();
        } else {
          body = {};
        }
        c.set('validatedBody', schemas.body.parse(body));
      }

      if (schemas.params) {
        c.set('validatedParams', schemas.params.parse(c.req.param()));
      }

      if (schemas.query) {
        c.set('validatedQuery', schemas.query.parse(c.req.query()));
      }

      await next();
    } catch (err) {
      if (err instanceof ZodError) {
        const details = err.errors.map(e => ({
          path: e.path.join('.'),
          message: e.message,
          code: e.code,
        }));
        throw new ValidationError('Validation failed', details);
      }
      throw err;
    }
  };
}

// ヘルパー: 型安全な取得
export function getValidatedBody<T>(c: Context): T {
  return (c as Context<any>).get('validatedBody') as T;
}
export function getValidatedParams<T>(c: Context): T {
  return (c as Context<any>).get('validatedParams') as T;
}
export function getValidatedQuery<T>(c: Context): T {
  return (c as Context<any>).get('validatedQuery') as T;
}