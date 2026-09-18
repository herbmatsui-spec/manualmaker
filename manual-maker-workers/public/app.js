import * as pdfjsLib from './pdfjs/pdf.min.mjs';

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL('./pdfjs/pdf.worker.min.mjs', import.meta.url).href;

const $ = (id) => document.getElementById(id);
const state = { file: null, fileName: 'manual', busy: false };
const statusEl = $('file-status');
const extractStatus = $('extract-status');
const fileInput = $('file-input');
const dropZone = $('drop-zone');

function setStatus(el, message, isError = false) {
  el.textContent = message;
  el.classList.toggle('error', isError);
}

function updateEditor() {
  $('char-count').textContent = String($('editor').value.length);
  for (const id of ['save-md', 'save-txt', 'print-pdf']) {
    $(id).disabled = state.busy || !$('editor').value.length;
  }
}

function setBusy(busy) {
  state.busy = busy;
  fileInput.disabled = busy;
  $('extract-button').disabled = busy;
  $('editor').disabled = busy;
  dropZone.setAttribute('aria-disabled', String(busy));
  updateEditor();
}

function handleFile(file) {
  if (!file || state.busy) return;
  if (!file.name.toLowerCase().endsWith('.pdf') || !file.size || file.size > 50 * 1024 * 1024) {
    setStatus(statusEl, '空でない50 MiB以下のPDFファイルを選択してください。', true);
    return;
  }
  if ($('editor').value && !window.confirm('編集中の内容を破棄して別のPDFを読み込みますか？')) return;
  state.file = file;
  state.fileName = file.name;
  $('editor').value = '';
  updateEditor();
  setStatus(statusEl, `選択済み: ${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MiB)`);
  $('extract-panel').classList.remove('hidden');
  $('edit-panel').classList.remove('hidden');
  setStatus(extractStatus, '「テキストを抽出」を押してください。手入力もできます。');
}

async function extractText() {
  if (!state.file || state.busy) return;
  if ($('editor').value && !window.confirm('編集中の内容を抽出結果で置き換えますか？')) return;
  setBusy(true);
  $('editor').value = '';
  updateEditor();
  setStatus(extractStatus, '抽出中...');
  let task;
  try {
    task = pdfjsLib.getDocument({
      data: await state.file.arrayBuffer(),
      cMapUrl: new URL('./pdfjs/cmaps/', import.meta.url).href,
      cMapPacked: true,
      isEvalSupported: false,
      useSystemFonts: true,
    });
    task.onPassword = () => {
      setStatus(extractStatus, 'パスワード保護されたPDFには対応していません。', true);
      void task.destroy();
    };
    const pdf = await task.promise;
    if (pdf.numPages > 300) throw new Error('300ページ以下のPDFを選択してください。');
    const pages = [];
    let chars = 0;
    let emptyPages = 0;
    for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
      const page = await pdf.getPage(pageNum);
      try {
        const content = await page.getTextContent();
        const text = content.items.filter((item) => 'str' in item)
          .map((item) => item.str + (item.hasEOL ? '\n' : ' ')).join('')
          .replace(/[ \t]+\n/g, '\n').trim();
        chars += text.length;
        if (chars > 2000000) throw new Error('抽出テキストが200万文字を超えました。PDFを分割してください。');
        if (text) pages.push(`## ページ ${pageNum}\n\n${text}`);
        else emptyPages++;
      } finally {
        page.cleanup();
      }
      setStatus(extractStatus, `抽出中... ${pageNum}/${pdf.numPages} ページ`);
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
    $('editor').value = pages.join('\n\n');
    $('edit-panel').classList.remove('hidden');
    setStatus(extractStatus, pages.length
      ? `抽出完了: ${pdf.numPages} ページ（文字のないページ: ${emptyPages}）。読み順・文字の誤りを確認してください。`
      : '抽出結果なし: テキスト層がありません。OCRは行いません。手入力で編集できます。', !pages.length);
  } catch (err) {
    setStatus(extractStatus, `抽出に失敗しました（破損・パスワード保護等）: ${err instanceof Error ? err.message : String(err)}`, true);
  } finally {
    try { await task?.destroy(); } finally { setBusy(false); }
  }
}

function saveFile(extension) {
  const base = state.fileName.replace(/\.pdf$/i, '').replace(/[\\/:*?"<>|\x00-\x1f]/g, '_') || 'manual';
  const text = $('editor').value;
  const blob = new Blob([text], { type: extension === 'md' ? 'text/markdown;charset=utf-8' : 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${base}.${extension}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

dropZone.addEventListener('click', () => { if (!state.busy) fileInput.click(); });
dropZone.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    if (!state.busy) fileInput.click();
  }
});
document.addEventListener('dragover', (e) => e.preventDefault());
document.addEventListener('drop', (e) => e.preventDefault());
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  handleFile(e.dataTransfer?.files[0]);
});
fileInput.addEventListener('change', () => { handleFile(fileInput.files[0]); fileInput.value = ''; });
$('extract-button').addEventListener('click', extractText);
$('editor').addEventListener('input', updateEditor);
$('save-md').addEventListener('click', () => saveFile('md'));
$('save-txt').addEventListener('click', () => saveFile('txt'));
window.addEventListener('beforeprint', () => { $('print-content').textContent = $('editor').value; });
$('print-pdf').addEventListener('click', () => window.print());
window.addEventListener('beforeunload', (e) => {
  if (state.busy || $('editor').value) { e.preventDefault(); e.returnValue = ''; }
});
