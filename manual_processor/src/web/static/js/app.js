// Client Application Logic for Manual Processor Web Dashboard

document.addEventListener('DOMContentLoaded', () => {
    let currentFileId = null;
    let ws = null;

    // DOM Elements
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const selectedFileInfo = document.getElementById('selected-file-info');
    const startBtn = document.getElementById('start-btn');
    const compactToggle = document.getElementById('compact-layout-toggle');
    const emojiToggle = document.getElementById('use-emojis-toggle');

    const progressSection = document.getElementById('progress-section');
    const progressFill = document.getElementById('progress-fill');
    const progressPercent = document.getElementById('progress-percent');
    const progressStage = document.getElementById('progress-stage');

    const summaryPlaceholder = document.getElementById('summary-placeholder');
    const summaryContent = document.getElementById('summary-content');
    const docTitle = document.getElementById('doc-title');
    const docSummary = document.getElementById('doc-summary');
    const docKeypoints = document.getElementById('doc-keypoints');

    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    const downloadBtns = document.querySelectorAll('.download-btn');

    // Tab Switching
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(btn.dataset.tab).classList.add('active');
        });
    });

    // Drag & Drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    // File Upload Handler
    async function handleFileUpload(file) {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            alert('PDFファイルを選択してください。');
            return;
        }

        selectedFileInfo.textContent = `選択中: ${file.name} (${(file.size / (1024 * 1024)).toFixed(2)} MB)`;
        startBtn.disabled = true;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'アップロード失敗');
            }

            const data = await res.json();
            currentFileId = data.file_id;
            startBtn.disabled = false;
            connectWebSocket(currentFileId);
        } catch (err) {
            alert(`エラー: ${err.message}`);
        }
    }

    // WebSocket Connection
    function connectWebSocket(fileId) {
        if (ws) ws.close();
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${protocol}//${window.location.host}/ws/progress/${fileId}`);

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.progress !== undefined) {
                updateProgress(data.progress, data.stage || '処理中...');
            }
        };
    }

    function updateProgress(percent, stage) {
        progressSection.style.display = 'block';
        progressFill.style.width = `${percent}%`;
        progressPercent.textContent = `${percent}%`;
        progressStage.textContent = stage;
    }

    // Start Processing
    startBtn.addEventListener('click', async () => {
        if (!currentFileId) return;

        startBtn.disabled = true;
        updateProgress(10, 'OCR & AI 解析を開始します...');

        try {
            const options = {
                compact_layout: compactToggle.checked,
                use_emojis: emojiToggle.checked
            };

            const res = await fetch(`/api/process/${currentFileId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(options)
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || '処理失敗');
            }

            const result = await res.json();
            updateProgress(100, '処理完了！');
            renderResults(result);
        } catch (err) {
            alert(`処理エラー: ${err.message}`);
            updateProgress(0, 'エラー発生');
        } finally {
            startBtn.disabled = false;
        }
    });

    // Render Results
    function renderResults(res) {
        if (!res.success) {
            alert(`エラー: ${res.error}`);
            return;
        }

        summaryPlaceholder.style.display = 'none';
        summaryContent.style.display = 'block';

        docTitle.textContent = res.title || '手書きマニュアル要約結果';
        docSummary.textContent = res.summary || '要約テキストなし';

        docKeypoints.innerHTML = '';
        (res.key_points || []).forEach(kp => {
            const li = document.createElement('li');
            li.textContent = kp;
            docKeypoints.appendChild(li);
        });

        // Enable Downloads
        downloadBtns.forEach(btn => {
            btn.disabled = false;
            btn.onclick = () => {
                const type = btn.dataset.type;
                window.open(`/api/download/${currentFileId}/${type}`, '_blank');
            };
        });

        // Mermaid preview if present
        if (res.mermaid_code) {
            const mermaidInput = document.getElementById('mermaid-code-input');
            if (mermaidInput) {
                mermaidInput.value = res.mermaid_code;
                renderMermaidPreview();
            }
        }
    }

    // Mermaid Editor & Live Preview Logic
    const renderBtn = document.getElementById('render-mermaid-btn');
    const mermaidInput = document.getElementById('mermaid-code-input');
    const mermaidTheme = document.getElementById('mermaid-theme');
    const previewImg = document.getElementById('mermaid-preview-img');
    const diagramPlaceholder = document.getElementById('diagram-placeholder');

    if (renderBtn) {
        renderBtn.addEventListener('click', renderMermaidPreview);
    }

    if (mermaidTheme) {
        mermaidTheme.addEventListener('change', renderMermaidPreview);
    }


    async function renderMermaidPreview() {
        const code = mermaidInput.value.trim();
        if (!code) return;

        renderBtn.disabled = true;
        diagramPlaceholder.textContent = 'レンダリング中...';
        diagramPlaceholder.style.display = 'block';

        try {
            const res = await fetch('/api/mermaid/render', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mermaid_code: code,
                    theme: mermaidTheme.value
                })
            });

            if (!res.ok) throw new Error('レンダリングエラー');

            const blob = await res.blob();
            const url = URL.createObjectURL(blob);

            previewImg.src = url;
            previewImg.style.display = 'block';
            diagramPlaceholder.style.display = 'none';
        } catch (err) {
            diagramPlaceholder.textContent = `エラー: ${err.message}`;
            diagramPlaceholder.style.display = 'block';
        } finally {
            renderBtn.disabled = false;
        }
    }

    // AI Regeneration Handler
    const aiRegenerateBtn = document.getElementById('ai-regenerate-btn');
    const aiInstructionInput = document.getElementById('ai-instruction');

    if (aiRegenerateBtn) {
        aiRegenerateBtn.addEventListener('click', async () => {
            const instruction = aiInstructionInput.value.trim();
            const currentCode = mermaidInput.value.trim();

            if (!instruction || !currentCode) {
                alert('修正指示を入力してください。');
                return;
            }

            aiRegenerateBtn.disabled = true;
            aiRegenerateBtn.textContent = 'AI 修正中...';

            try {
                const res = await fetch('/api/mermaid/regenerate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        current_code: currentCode,
                        instruction: instruction
                    })
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || '再生成失敗');
                }

                const data = await res.json();
                if (data.mermaid_code) {
                    mermaidInput.value = data.mermaid_code;
                    renderMermaidPreview();
                    aiInstructionInput.value = '';
                }
            } catch (err) {
                alert(`AI 再生成エラー: ${err.message}`);
            } finally {
                aiRegenerateBtn.disabled = false;
                aiRegenerateBtn.textContent = '修正指示';
            }
        });
    }
});


