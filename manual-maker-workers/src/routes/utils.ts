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
  return /^[a-f0-9]{32}$/.test(fileId);
}

export function getContentType(type: string): string {
  const contentTypes: Record<string, string> = {
    pdf: 'application/pdf',
    docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    audio: 'audio/mpeg',
    mp3: 'audio/mpeg',
    diagram: 'image/png',
    png: 'image/png'
  };
  return contentTypes[type] || 'application/octet-stream';
}

export async function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}
