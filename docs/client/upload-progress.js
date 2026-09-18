/** Browser example. The returned function cancels the client request, not server storage. */
export function uploadPdf(file, {
  onProgress = () => {},
  onSaving = () => {},
  onComplete = () => {},
  onError = () => {},
  onCancel = () => {},
} = {}) {
  const xhr = new XMLHttpRequest();
  xhr.upload.onprogress = (event) => {
    onProgress(event.lengthComputable && event.total > 0
      ? Math.min(100, Math.round(event.loaded / event.total * 100))
      : null);
  };
  xhr.upload.onload = () => onSaving();
  xhr.onload = () => {
    if (xhr.status < 200 || xhr.status >= 300) {
      onError({ status: xhr.status, retryAfter: xhr.getResponseHeader('Retry-After') });
      return;
    }
    let metadata;
    try {
      metadata = JSON.parse(xhr.responseText);
    } catch {
      onError({ status: xhr.status, message: 'Invalid server response' });
      return;
    }
    onComplete(metadata);
  };
  xhr.onerror = () => onError({ status: 0, message: 'Network error; check uploads before retrying' });
  xhr.ontimeout = () => onError({ status: 0, message: 'Upload timed out; check uploads before retrying' });
  xhr.onabort = () => onCancel();
  xhr.open('POST', '/api/upload');
  xhr.timeout = 10 * 60 * 1000;
  const form = new FormData();
  form.append('file', file);
  xhr.send(form);
  return () => xhr.abort();
}
