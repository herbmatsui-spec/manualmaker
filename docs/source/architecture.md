# Architecture

Manual Processor はレイヤードアーキテクチャを採用しています。

```
┌─────────────────────────────────────────────┐
│  Presentation Layer                          │
│  - Web UI (FastAPI + Jinja2)                 │
│  - GUI (Tkinter)                             │
│  - CLI                                       │
└─────────────────────────────────────────────┘
              │
┌─────────────────────────────────────────────┐
│  Orchestration Layer                         │
│  - DocumentOrchestrator (queue + workers)    │
│  - BatchProcessor                            │
│  - USB Monitor                               │
└─────────────────────────────────────────────┘
              │
┌─────────────────────────────────────────────┐
│  Processing Layer                            │
│  - OCR (Vision API / Gemini multimodal)      │
│  - GeminiProcessor (summary + structure)     │
│  - PromptBuilder                             │
│  - SecurityManager (PII masking)             │
└─────────────────────────────────────────────┘
              │
┌─────────────────────────────────────────────┐
│  Output Layer                                │
│  - PDF / DOCX / Audio / Diagram generators   │
│  - OutputManager                             │
│  - QRGenerator                               │
└─────────────────────────────────────────────┘
              │
┌─────────────────────────────────────────────┐
│  Cross-Cutting Concerns                      │
│  - Observability (Prometheus metrics)        │
│  - CacheManager                              │
│  - I18nManager                               │
│  - Logger + AuditLogger                      │
└─────────────────────────────────────────────┘
```

## 主要データモデル

- `Section` — マニュアル内の章・節
- `GeminiResult` — Gemini 出力の構造化データ(title, summary, key_points, sections, glossary)
- `ProcessingResult` — オーケストレータの結果
- `OutputFiles` / `OutputConfig` — 出力ファイル情報

## 設定システム

- `config/config.py` の `AppConfig.get_instance()` がシングルトン
- YAML + 環境変数 + Pydantic-settings で階層的に解決
- `config/watcher.py` でホットリロード可能