/**
 * Utility functions
 */
export function uuidv4(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

export function validateFileId(fileId: string): boolean {
  return /^[a-f0-9]{32}$/.test(fileId) || /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(fileId);
}

export function getContentType(type: string): string {
  const contentTypes: Record<string, string> = {
    pdf: 'application/pdf',
    docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    audio: 'audio/mpeg',
    mp3: 'audio/mpeg',
    diagram: 'image/png',
    png: 'image/png',
    md: 'text/markdown; charset=utf-8',
    markdown: 'text/markdown; charset=utf-8',
    html: 'text/html; charset=utf-8',
    json: 'application/json'
  };
  return contentTypes[type] || 'application/octet-stream';
}

export async function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

export function sanitizeFilename(filename: string): string {
  // Path traversal prevention
  const clean = filename.replace(/[\\/]/g, '_').replace(/\.\.+/g, '_');
  // Remove control characters
  return clean.replace(/[\x00-\x1f\x7f]/g, '');
}

export function isValidFilename(filename: string): boolean {
  const sanitized = sanitizeFilename(filename);
  return sanitized === filename &&
    /^[a-zA-Z0-9._\-\u3000-\u9faf\u3040-\u309f\u30a0-\u30ff（）　]+\.pdf$/i.test(filename);
}