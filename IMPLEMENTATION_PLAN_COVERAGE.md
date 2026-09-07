# Manual Processor カバレッジ向上 実装計画書 v1.0

**作成日**: 2026-09-07
**対象バージョン**: Manual Processor v2.2.0
**Baseline**: 558 tests passed, **coverage 69%**
**目標**: **85%以上** (CI gate を段階的に引き上げ、最終的に `fail_under=85`)
**総未カバー行数**: 約 1,616 行 / 5,183 statements

---

## 全体方針

1. **低リスク・高効果**: 純粋関数・モックしやすいモジュールから着手
2. **高リスクは分離**: OS依存 (usb_monitor) / GUI (gui/main.py) / 暗号化 (keyring) は skip マーカーで除外も検討
3. **段階的 CI ゲート**: 70 → 75 → 80 → 85 と引き上げ
4. **各 Step 完了時に**: 全テスト pass + 対象モジュール単独カバレッジ + 全体カバレッジ を記録

---

## 優先度分類

### 🔴 Phase 1: 最優先 (目標 +5%, リスク低〜中)

| Step | ファイル | 現在 | 目標 | 工数 |
|------|---------|------|------|------|
| 1 | `audio_generator.py` | 20% | 85% | 1.5h |
| 2 | `config/watcher.py` | 0% | 90% | 1h |
| 3 | `config/validate.py` | 67% | 90% | 0.5h |
| 4 | `batch_processor.py` | 39% | 80% | 1.5h |
| 5 | `cache_manager.py` | 63% | 85% | 1h |

### 🟡 Phase 2: 中優先 (目標 +6%)

| Step | ファイル | 現在 | 目標 | 工数 |
|------|---------|------|------|------|
| 6 | `diagram_generator.py` | 65% | 85% | 2h |
| 7 | `docx_generator.py` | 66% | 85% | 1.5h |
| 8 | `pdf_generator.py` | 67% | 90% | 1.5h |
| 9 | `gemini_processor.py` | 55% | 80% | 2h |
| 10 | `security_manager.py` | 60% | 85% | 2h |

### 🟢 Phase 3: 高優先だが難所 (目標 +5%)

| Step | ファイル | 現在 | 目標 | 工数 |
|------|---------|------|------|------|
| 11 | `processor.py` | 62% | 85% | 3h |
| 12 | `web/app.py` | 54% | 75% | 3h |
| 13 | `usb_monitor.py` | 53% | 70% (skip併用) | 2h |
| 14 | `keyring_store.py` | 28% | 60% (mock で) | 1.5h |

### ⚪ Phase 4: 微調整 (目標 +1〜2%)

| Step | ファイル | 現在 | 目標 | 工数 |
|------|---------|------|------|------|
| 15 | `audit_logger.py` | 73% | 90% | 0.5h |
| 16 | `processor_factory.py` | 75% | 95% | 0.5h |
| 17 | `progress_manager.py` | 76% | 95% | 0.5h |
| 18 | `output_plugin.py` | 88% | 95% | 0.3h |
| 19 | `log_filter.py` | 57% | 90% | 0.5h |
| 20 | `path_resolver.py` | 70% | 95% | 0.2h |
| 21 | `ocr_processor.py` | 80% | 90% | 0.5h |
| 22 | `pdf_processor.py` | 85% | 95% | 0.5h |

### ⚠️ Phase 5: 対応困難 (skip 推奨 or 部分対応)

| Step | ファイル | 現在 | 目標 | 備考 |
|------|---------|------|------|------|
| 23 | `gui/main.py` | 0% | skip | Tkinter依存。`pytest.skip` で除外 |
| 24 | `config/config.py` | 69% | 80% | setter 経路を追加 |

---

## ステップ詳細

### Step 1: audio_generator.py (20% → 85%)

**目標**: TTS (Text-to-Speech) 周りのテスト。`gTTS`, `edge-tts`, `pydub`, Google Cloud TTS のフォールバック経路をモックで全カバー。

**新規テスト**: `tests/test_audio_generator.py`
- `AudioGenerator.__init__` の language/voice/speaking_rate/pitch 設定
- `generate_audio` 正常系 (edge-tts成功, gTTS成功, fallback)
- `generate_audio` 失敗系 (TTSError, network error, file write error)
- `pydub` によるフォーマット変換 (mp3 ↔ wav)
- デフォルト language_code "ja-JP" のフォールバック

**検証**:
```bash
python -m pytest tests/test_audio_generator.py --cov=src/audio_generator --cov-fail-under=85 -v
```

---

### Step 2: config/watcher.py (0% → 90%)

**目標**: watchdog の FileSystemEventHandler のテスト。`watchdog` 未インストール時のフォールバックも含めてカバー。

**新規テスト**: `tests/test_config_watcher.py`
- `ConfigWatcher.__init__` のハンドラ設定
- `_on_modified` / `on_any_event` のディスパッチ
- ファイル変更時の callback 呼び出し
- 例外発生時のログ記録と握りつぶし
- `start()` / `stop()` の lifecycle
- watchdog 不在時の fallback (polling mode)

**検証**: 同上

---

### Step 3: config/validate.py (67% → 90%)

**目標**: `validate_config` CLI コマンドのテスト。`sys.argv` のモック、`Config.get_instance()` の mock。

**新規テスト**: `tests/test_config_validate.py`
- 正常系 (全項目pass, exit 0)
- エラーあり (exit 1)
- `--json` フラグ
- `--strict` フラグ
- 空のconfig → デフォルト動作

**検証**: 同上

---

### Step 4: batch_processor.py (39% → 80%)

**目標**: 優先度付きキューのテスト。threading 周りは `threading.Event` で同期確認。

**新規テスト**: `tests/test_batch_processor.py`
- `BatchProcessor.__init__` デフォルト引数
- `add_task` / `get_next_task` / `complete_task`
- 優先度ソート
- 同時実行数の制御 (`max_concurrent`)
- ワーカースレッドの起動・停止
- タスク失敗時のエラーハンドリング
- キュー空時の `get_next_task` ブロック

**検証**: 同上

---

### Step 5: cache_manager.py (63% → 85%)

**目標**: LRU + ディスク2層キャッシュのテスト。

**新規テスト**: `tests/test_cache_manager.py`
- `LRUCache.put` / `get` / `evict`
- `LRUCache.clear` / `__len__`
- `DiskCache.put` / `get` (tmp_path fixture)
- TTL 期限切れ
- ファイル破損時の graceful 回復
- `CacheManager` 階層キャッシュ (mem → disk)

**検証**: 同上

---

### Step 6-10: Phase 2 モジュール群

各ファイルの実装を読み、未カバーの分岐を埋めるテストを追加。
詳細は実装時に決定。

---

### Step 11: processor.py (62% → 85%) ⚠️ 最大ボリューム

**目標**: `DocumentProcessor` の全メソッド網羅。280 statements のうち 106 が未カバー。

**主な未カバー領域** (分析済み):
- `68, 71`: エラーパス
- `76-78, 85-87`: OCR失敗時のリトライ
- `98, 103, 107-110`: API timeout
- `153-167`: 画像抽出 (`fitz` 関連)
- `172-174, 181-189`: テキスト前処理
- `195-201`: 要約生成
- `328-360`: フローチャート生成
- `370-372`: ファイル保存
- `411-412, 423-425, 436-438`: 後処理

**新規テスト**: `tests/test_processor.py` 拡張
- `_extract_text_from_pdf` のすべてのエラーパス
- `process_pdf` のサニタイズ (XSS 対策)
- 大きなPDF (100ページ) のチャンク分割
- 部分失敗 (`test_processor_partial_failure.py` 既存を統合)

**検証**: 同上

---

### Step 12: web/app.py (54% → 75%) ⚠️ API 多様

**目標**: FastAPI 全エンドポイントのテスト。既に `test_web_api.py` + `test_e2e/test_web_ui.py` があるが、未カバーのアップロード系・Drive系を埋める。

**追加テスト**:
- `/api/upload` 正常系・サイズ超過・拡張子不正
- `/api/progress/{file_id}` SSE / WebSocket
- `/api/process/options` POST
- `/api/download/{file_id}/{format}` 全 format
- `/api/security/mask`, `/api/security/audit`
- `/api/drive/*` 各エンドポイント (Drive manager は mock)
- `/api/mermaid/render`, `/api/mermaid/regenerate`, `/api/mermaid/save`

**検証**: 同上

---

### Step 13: usb_monitor.py (53% → 70%)

**目標**: watchdog ベースの USB 監視のテスト。`watchdog` を mock で再現。

**追加テスト**:
- USBFileHandler.on_created / on_modified / on_deleted / on_moved
- パターンマッチ (.pdf のみ)
- USB デバイス挿抜イベント
- `_scan_existing_files` 初回スキャン
- polling モード (watchdog 不在時)
- callback の正常/異常呼び出し

**検証**: 同上

---

### Step 14: keyring_store.py (28% → 60%)

**目標**: keyring の save/load/delete のテスト。`keyring` を完全 mock。

**追加テスト**:
- `save_api_key` 正常
- `save_api_key` 失敗時 (PermissionError)
- `load_api_key` ヒット / ミス
- `delete_api_key` 成功 / 既に削除済み
- keyring 不在時の fallback (環境変数)

**検証**: 同上

---

### Step 15-22: 微調整 (省略、各 0.5h 以内)

各モジュールの `missing_lines` を直接読んでテストケースを書く。

---

### Step 23: gui/main.py (0% → skip)

**対応**: `tests/test_gui_main.py` を作成し、`pytest.importorskip("tkinter")` で環境依存を skip。
CI マトリクスで Tkinter を含むランナー (Ubuntu, macOS) のみ実テストする方針。

---

### Step 24: config/config.py (69% → 80%)

**目標**: setter 経路 (CLI から `apply_prompt_cli_options`) のテスト。

**追加テスト**:
- `prompt_layout` / `prompt_domain_terms` / `prompt_has_diagrams` setter
- `output_directory` setter (Step C で追加済み)
- `from_env` の各 env 変数

---

## CI ゲート引き上げ計画

| マイルストーン | fail_under | 想定 Module 完了 |
|---------------|-----------|------------------|
| 即時 | 70 | (既存) |
| Phase 1 完了 | 75 | Steps 1-5 |
| Phase 2 完了 | 80 | Steps 6-10 |
| Phase 3 完了 | 85 | Steps 11-14 |
| Phase 4 完了 | 87 | Steps 15-22 |
| Phase 5 完了 | 90 | Steps 23-24 |

---

## 各 Step 共通テンプレート

```bash
# 1. 対象テストのみ実行 (速いフィードバック)
python -m pytest tests/test_<module>.py -v

# 2. 対象モジュール単独カバレッジ
python -m pytest tests/test_<module>.py \
    --cov=src.<module> --cov-report=term-missing

# 3. 全テスト + 全体カバレッジ (回帰チェック)
python -m pytest tests/ --cov=src --cov=config \
    --cov-report=term --cov-fail-under=<current_threshold>
```

---

## 推定効果

| Phase | モジュール数 | 推定 +% | 累積カバレッジ |
|-------|--------------|---------|----------------|
| Baseline | - | - | 69% |
| Phase 1 | 5 | +5% | 74% |
| Phase 2 | 5 | +6% | 80% |
| Phase 3 | 4 | +5% | 85% |
| Phase 4 | 8 | +3% | 88% |
| Phase 5 | 2 | +1% | 89% |

---

## リスク管理

- **破壊的変更**: テストのみ追加し、ソースコードは変更しない方針
- **Flaky test**: `time`, `threading`, `random` を mock して決定的化
- **API呼び出し**: 全て `unittest.mock` で patch、CI で実際に API を呼ばない
- **GUI**: Tkinter skip で対応、Phase 5 で扱う

---

## スケジュール目安

| Phase | 工数 | 推奨日数 |
|-------|------|----------|
| Phase 1 | 5.5h | 1日 |
| Phase 2 | 9h | 1.5日 |
| Phase 3 | 9.5h | 2日 |
| Phase 4 | 3.5h | 0.5日 |
| Phase 5 | 1.5h | 0.5日 |
| **合計** | **29h** | **5.5日** |

---

## 完了基準 (DoD)

- [ ] 全体カバレッジ 85%以上
- [ ] CI ゲート `fail_under=85` 通過
- [ ] 新規追加テスト全件 pass
- [ ] 既存テストの regression 0
- [ ] カバレッジレポート (`htmlcov/`) がコミット artifact に含まれる

---

**承認後、Phase 1 Step 1 から実装開始予定。**