# Manual Processor 完成度向上実装計画書 v1.0

**作成日**: 2026-09-07
**対象バージョン**: Manual Processor v2.1.0
**対象改善案**: 提案 #2〜#7
**Baseline**: 483 tests passed (33.93s), coverage 63%

---

## 全体方針

各ステップは **実装 → 検証 → 必要に応じて修正** のサイクルで進める。
各ステップ完了時に以下を確認する:
1. `python -m pytest manual_processor/tests/ -q` が全件 pass
2. `python -m pytest --cov=manual_processor/src --cov=manual_processor/config` カバレッジが悪化していないこと
3. 該当 Step の動作確認

実装順序は **低リスク → 高リスク** および **即時効果 → 長期投資** で並べる。

---

## 実装順序と概要

| Step | 改善案 | タイトル | 工数目安 | リスク |
|------|--------|----------|---------|--------|
| A | #3 | 依存関係・設定のクリーンアップ | 0.5h | 低 |
| B | #4 | リポジトリ衛生 (.gitignore + クリーンアップ) | 0.5h | 低 |
| C | #2 | カバレッジ0%モジュール撲滅 + CIゲート化 | 4h | 中 |
| D | #6 | 観測性統合 (OpenTelemetry + /metrics) | 3h | 中 |
| E | #7 | Docs as Code (mkdocs-material) | 2h | 低 |
| F | #5 | Playwright E2E 導入 | 3h | 中 |

---

## Step A: 依存関係・設定のクリーンアップ

### 目標
- 誤った依存名 `mermaidx>=0.3.0` を削除
- 旧メインファイル `src/manual_processor/main.py` を削除
- `config/config_new.py` を `config/config.py` に統合し shim 削除
- `pyproject.toml` の classifiers を Production/Stable に

### 変更ファイル
1. `manual_processor/pyproject.toml` — `mermaidx` 依存削除、classifiers 更新
2. `manual_processor/src/manual_processor/main.py` — 削除
3. `manual_processor/config/config.py` — config_new の内容を取り込み
4. `manual_processor/config/config_new.py` — 削除

### 検証手順
```bash
python -m pytest manual_processor/tests/ -q
python -c "from config.config import Config; print(Config.get_instance().gemini_model_name)"
```
期待値: 全テストpass、旧importが壊れていない

---

## Step B: リポジトリ衛生

### 目標
- `.gitignore` を強化して `temp/`, `__pycache__/`, `build/`, `.egg-info/`, `.benchmarks/`, `logs/*.log`, ノイズファイルを除外
- `scripts/clean_repo.py` 作成（追跡不要なものを一括削除）
- 既存追跡ファイルを `git rm --cached` でインデックスから外す

### 変更ファイル
1. `.gitignore` — 強化版で上書き
2. `manual_processor/scripts/clean_repo.py` — 新規
3. `git rm --cached` でノイズファイル群を除外

### 検証手順
```bash
git status | head -50
python manual_processor/scripts/clean_repo.py --dry-run
python -m pytest manual_processor/tests/ -q
```
期待値: 追跡ファイルからtemp/ pyc egg-info等が消える、テスト全pass

---

## Step C: カバレッジ0%モジュール撲滅

### 目標
以下モジュールのカバレッジを 80%以上に引き上げる:
- `src/gemini_ocr.py` (0% → 80%)
- `src/gui/main.py` (0% → 60%、Tkinter依存のためlimit付き)
- `src/output_manager.py` (0% → 85%)
- `src/prompt_engine/prompt_cache.py` (0% → 85%)
- `src/utils/result_formatter.py` (0% → 90%)
- `src/processor/processor.py` (62% → 80%)
- `src/gemini_processor.py` (55% → 80%)

### 追加依存 (requirements-dev.txt)
- `pytest-asyncio>=0.23`
- `freezegun>=1.5`
- `pytest-httpx>=0.30`

### 新規/拡張テストファイル
- `manual_processor/tests/test_gemini_ocr.py`
- `manual_processor/tests/test_gui_main.py` (Tkinter skip対応)
- `manual_processor/tests/test_output_manager.py`
- `manual_processor/tests/test_prompt_cache.py`
- `manual_processor/tests/test_result_formatter.py`
- `manual_processor/tests/test_processor_comprehensive.py` (processor.py, gemini_processor.pyの隙間を埋める)
- `manual_processor/tests/conftest.py` — 共通fixture拡張

### CI ゲート化
- `pyproject.toml` の `[tool.coverage.report]` に `fail_under = 80`
- `Makefile` の `coverage-check` を更新

### 検証手順
```bash
python -m pytest manual_processor/tests/ -q
python -m pytest manual_processor/tests/ --cov=manual_processor/src --cov=manual_processor/config --cov-fail-under=80
```
期待値: 全テストpass、カバレッジ80%以上、未達は明示

---

## Step D: 観測性統合

### 目標
- OpenTelemetry SDK を導入し、OCR/生成処理に Span を追加
- `/metrics` Prometheus エンドポイント追加
- 主要メトリクス: `manual_processor_jobs_total`, `manual_processor_job_duration_seconds`, `manual_processor_api_errors_total`

### 変更ファイル
1. `manual_processor/pyproject.toml` — opentelemetry 追加
2. `manual_processor/src/observability/__init__.py` — 新規パッケージ
3. `manual_processor/src/observability/tracing.py` — Tracer セットアップ
4. `manual_processor/src/observability/metrics.py` — メトリクス定義
5. `manual_processor/src/orchestrator.py` — Span 計装
6. `manual_processor/src/web/app.py` — `/metrics` 追加

### 検証手順
```bash
python -m pytest manual_processor/tests/ -q
python -c "from src.observability import get_tracer, get_metrics; print('OK')"
```
期待値: テスト全pass、import成功

---

## Step E: Docs as Code

### 目標
- `mkdocs-material` を dev 依存に追加
- `docs/source/` に Getting Started / Architecture / API / Deployment / Contributing を再構成
- `mkdocstrings` で docstring → API リファレンス自動生成

### 変更ファイル
1. `manual_processor/pyproject.toml` — mkdocs 系追加
2. `docs/source/index.md` — 新規
3. `docs/source/getting-started.md` — 新規
4. `docs/source/architecture.md` — 新規
5. `docs/source/api/index.md` — 新規
6. `docs/source/deployment.md` — 新規
7. `docs/source/contributing.md` — 新規
8. `manual_processor/mkdocs.yml` — 新規

### 検証手順
```bash
python -m mkdocs build --config-file manual_processor/mkdocs.yml --strict
```
期待値: `docs/site/index.html` が生成される

---

## Step F: Playwright E2E

### 目標
- `tests/e2e/` に Playwright を導入
- シナリオ: アップロード → 進捗 → ダウンロード → Mermaid編集 → エラー時のリカバリ
- CI で `pytest --headed=false` 実行

### 変更ファイル
1. `manual_processor/pyproject.toml` — playwright + pytest-playwright
2. `manual_processor/tests/e2e/test_web_ui.py` — 新規
3. `.github/workflows/test.yml` — Playwright install ステップ追加

### 検証手順
```bash
python -m pytest manual_processor/tests/e2e/test_web_ui.py --headed=false
```
期待値: E2E シナリオ pass

---

## 検証サマリ（全Step完了後）

```bash
# 全テスト + カバレッジ
python -m pytest manual_processor/tests/ --cov=manual_processor/src --cov=manual_processor/config --cov-fail-under=80

# Lint (既存)
python -m bandit -r manual_processor/src manual_processor/config

# ビルド検証
python -m mkdocs build --config-file manual_processor/mkdocs.yml --strict

# Docs反映チェック
ls docs/site/
```

---

## ロールバック戦略

各 Step は独立コミット可能。問題発生時は該当Stepの `git revert` で切り戻し。

---

**承認後、Step A から実装開始。**