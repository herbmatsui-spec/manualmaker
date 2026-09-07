# 手書きマニュアル処理システム 実装計画書 v2.0

## 概要

本ドキュメントは、完成度が低い9つの機能を実現不可能な小さなステップ(1-72)に分割し、低性能LLMでも確実に実装できる程度の粒度で記述したものである。

---

## 1. USB自動読み込み機能 (Steps 1-12)

**現在地**: Windows pywin32 による基本ポーリングのみ、watchdog 未使用

### Step 1: watchdog 依存関係の追加
- ファイル: `requirements.txt` を確認
- `watchdog` を追加（まだなければ）
- 追加後の pip install を実行

### Step 2: USBMonitor クラスに watchdog observer 追加
- ファイル: `src/usb_monitor.py`
- `self._observer = None` を `__init__` に追加
- `self._watched_paths = set(self.paths)` を追加

### Step 3: FileSystemEventHandler サブクラス作成
- `src/usb_monitor.py` に内部クラス `USBFileHandler` を追加
- `on_created(self, event)` メソッドを実装
- `on_modified(self, event)` メソッドを実装

### Step 4: start() メソッド watchdog 対応化
- `src/usb_monitor.py` の `start()` を修正
- `from watchdog.observers import Observer` をインポート
- `self._observer = Observer()` で observer 作成
- `self._observer.schedule(USBFileHandler(self.callback), path, recursive=True)` で登録
- `self._observer.start()` で監視開始

### Step 5: stop() メソッド watchdog 対応化
- `src/usb_monitor.py` の `stop()` を修正
- `if self._observer: self._observer.stop(); self._observer.join()`

### Step 6: 新規USB検出Interval調整
- `_monitor_loop` の sleep時間を 3.0秒から 1.0秒に変更
- コメント追加: 「watchdog が届かないイベント用フォールバック」

### Step 7: USB拔除検出追加
- `_monitor_loop` に拔除検出ロジック追加
- 存在しなくなった path を `_watched_paths` から削除
- ログ出力追加

### Step 8: エラー処理强化
- `start()` で observer 作成失敗時の try-except 追加
- 失敗時はpollingモードにフォールバック

### Step 9: 設定ファイルに監視対象扩展
- `config/config.py` を確認
- `usb_auto_detect: bool = True` 設定を追加（まだなければ）
- `usb_poll_interval: float = 1.0` 設定を追加

### Step 10: テスト用モック追加
- `tests/test_usb_monitor.py` に watchdog 使用テスト追加
- `test_watchdog_observer_starts` 関数作成
- `test_watchdog_file_callback` 関数作成

### Step 11: ドキュメント更新
- `README.md` のUSB監視機能説明を更新
- 使用例を記載

### Step 12: 統合テスト
- 実際のUSBメモリでテスト（可能であれば）
- 拔除・挿入イベントの検出確認

---

## 2. 多言語(i18n)サポート (Steps 13-22)

**現在地**: 日本語/英語の辞書のみ、Auto Language Detection が文字数ベース

### Step 13: i18n 辞書データ扩充
- ファイル: `src/i18n_manager.py`
- `TRANSLATIONS` 辞書に以下を追加:
  - `zh` (中国語簡体字)
  - `ko` (韓国語)
  - `es` (スペイン語)

### Step 14: detect_language 拡張
- `detect_language` メソッドの強化
- 日本語: `\u3040-\u9fff` (ひらがな・カタカナ・漢字)
- 中国語簡体字: `\u4e00-\u9fff`
- 韓国語: `\ac00-\ud7af`
- スペイン語: `\u00c0-\u00ff` 範囲のアクセント文字

### Step 15: 設定にデフォルト言語追加
- `config/config.py` に `default_language: str = "ja"` 追加
- 環境変数 `APP_LANGUAGE` での上書き対応

### Step 16: set_language メソッド追加
- `I18nManager` に `set_language(lang: str)` メソッド追加
- `self.current_lang = lang.lower()` のみ

### Step 17: get_available_languages メソッド追加
- `I18nManager` に `get_available_languages() -> List[str]` 追加
- `return list(TRANSLATIONS.keys())`

### Step 18: translate 用語集対応
- `TRANSLATIONS["ja"]` に `glossary_title`, `keyword_title` 等を追加
- 他の言語辞書にも同じキーを追加

### Step 19: GUI i18n 対応
- `src/gui/main.py` の `setup_ui` を修正
- メニューに言語選択を追加
- 選択時に `i18n_manager.set_language()` 呼び出し

### Step 20: Web UI i18n 対応
- `src/web/app.py` に `/api/i18n/languages` エンドポイント追加
- `src/web/app.py` に `/api/i18n/set` エンドポイント追加

### Step 21: テスト追加
- `tests/test_i18n.py` 新規作成
- `test_detect_japanese`, `test_detect_english` テスト追加
- `test_detect_chinese`, `test_detect_korean` テスト追加

### Step 22: README 更新
- 対応言語一覧を記載
- 設定方法を記載

---

## 3. カスタマイズ可能出力テンプレート (Steps 23-34)

**現在地**: `compact_layout`/`use_emojis` オプションのみ

### Step 23: テンプレートディレクトリ作成
- `manual_processor/templates/` ディレクトリ作成
- `pdf/` と `docx/` サブディレクトリ作成

### Step 24: PDFテンプレート基本構造定義
- `templates/pdf/default.json` 作成
- 構造:
  ```json
  {
    "name": "default",
    "layout": "standard",
    "sections_order": ["title", "summary", "key_points", "sections", "glossary"],
    "font_size": 11,
    "margin": 20
  }
  ```

### Step 25: PDF compact テンプレート追加
- `templates/pdf/compact.json` 作成
- 構造: `layout: "compact"`, `font_size: 13`, `margin: 12`

### Step 26: PDF テンプレートローダー追加
- `src/pdf_generator.py` に `TemplateLoader` クラス追加
- `load_template(name: str) -> dict` メソッド追加
- ファイルPATH: `templates/pdf/{name}.json`

### Step 27: apply_template_to_content 関数追加
- `src/pdf_generator.py` に `apply_template` 関数追加
- `sections_order` に基づいて content_lines を並び替え

### Step 28: create_formatted_pdf テンプレート対応化
- `compact_layout` の代わりに `template_name: str = "default"` パラメータに変更
- テンプレート適用ロジックを組み込み

### Step 29: Wordテンプレートディレクトリ作成
- `templates/docx/default.xml` 作成（Word XML テンプレート）

### Step 30: docx_generator テンプレート対応化
- `src/docx_generator.py` に `TemplateLoader` クラス追加
- `create_word_document` に `template_name` パラメータ追加

### Step 31: テンプレート継承機能追加
- `templates/pdf/default.json` に `parent: null` フィールド追加
- テンプレートローダーに `resolve_template(template) -> dict` メソッド追加
- parent が 있다면再帰的にマージ

### Step 32: テンプレート検証関数追加
- `src/pdf_generator.py` に `validate_template(template: dict) -> Tuple[bool, str]` 追加
- 必須フィールド確認
- `sections_order` の妥当性確認

### Step 33: プレビュー機能追加
- `src/web/app.py` に `/api/template/preview/{template_name}` エンドポイント追加
- テンプレート設定をJSONで返す

### Step 34: テスト追加
- `tests/test_template.py` 新規作成
- `test_load_default_template` テスト追加
- `test_template_inheritance` テスト追加
- `test_validate_template` テスト追加

---

## 4. セキュリティ/プライバシー (Steps 35-44)

**現在地**: PII masking のみ、暗号化なし、GDPR対応不完全

### Step 35: 追加PIIパターンを定義
- `src/security_manager.py` の `PATTERNS` に以下を追加:
  - 日本の銀行口座: `\d{6}-\d{8}`
  - マイナンバー: `\d{4}-\d{4}-\d{4}`
  - パスポート番号: `[A-Z]{1,2}\d{7}`

### Step 36: mask_sensitive_data 返回値扩充
- `mask_sensitive_data` の戻り値 `Dict[str, int]` を `Dict[str, Any]` に変更
- `counts` に加えて `masked_positions: List[Dict]` を追加
- 各マスク位置の (start, end, type) を記録

### Step 37: unmask_data 関数追加
- `src/security_manager.py` に `unmask_data(masked_text: str, original_positions: List[Dict]) -> str` 追加
- マスク解除機能

### Step 38: 設定に暗号化オプション追加
- `config/config.py` に `enable_encryption: bool = False` 追加
- `encryption_key_env: str = "ENCRYPTION_KEY"` 追加

### Step 39: 暗号化ユーティリティ追加
- `src/security_manager.py` に `_encrypt_bytes(data: bytes, key: bytes) -> bytes` 追加
- `src/security_manager.py` に `_decrypt_bytes(data: bytes, key: bytes) -> bytes` 追加
- AES暗号使用（`from cryptography.fernet import Fernet`）

### Step 40: 一時ファイル自動削除追加
- `src/security_manager.py` に `secure_delete(file_path: Path)` メソッド追加
- ファイル内容をランダムデータで上書き後削除

### Step 41: AuditLogger クラス追加
- `src/security_manager.py` に `AuditLogger` クラス追加
- `log_access(user_id: str, action: str, resource: str)` メソッド追加
- ログを `logs/audit.log` に出力

### Step 42: GDPR対応関数追加
- `src/security_manager.py` に `export_user_data(user_id: str) -> Dict` 追加
- `src/security_manager.py` に `delete_user_data(user_id: str) -> bool` 追加

### Step 43: セキュリティ設定確認エンドポイント追加
- `src/web/app.py` に `/api/security/status` エンドポイント追加
- 現在の PII masking 有効/無効状態返す

### Step 44: テスト追加
- `tests/test_security_manager.py` 新規作成
- `test_mask_phone_number` テスト追加
- `test_mask_credit_card` テスト追加
- `test_encrypt_decrypt` テスト追加
- `test_audit_log` テスト追加

---

## 5. パッケージング/配布 (Steps 45-52)

**現在地**: `build_exe.py`, `installer.iss` あり、CI/CD なし

### Step 45: pyproject.toml 作成
- プロジェクトルートに `pyproject.toml` 作成
- `setuptools` 設定記述
- 依存ライブラリ一覧記載

### Step 46: __version__ 統一
- `src/__init__.py` に `__version__ = "2.1.0"` 追加
- `config/config.py` の Config クラスでも参照

### Step 47: setup.py/setup.cfg 更新
- `setup.py` 確認・更新
- `entry_points` に `console_scripts` 追加
- `python main.py` 用のエントリーポイント設定

### Step 48: GitHub Actions ワークフロー作成
- `.github/workflows/build.yml` 作成
- Python バージョン matrix (3.8, 3.9, 3.10, 3.11)
- テスト実行ステップ追加
- wheel ビルドステップ追加

### Step 49: リリース用タグ付けスクリプト作成
- `scripts/release.sh` 作成
- `git tag v{version}` 実行
- GitHub release 作成 (gh CLI 使用)

### Step 50: ビルド成果物チェック
- `dist/` に `.exe` が生成されるか確認
- 依存ライブラリがすべて含まれているか確認

### Step 51: 署名・チェックサム追加
- `scripts/checksum.py` 作成
- SHA256 チェックサム計算・記録

### Step 52: ドキュメント整備
- `CHANGELOG.md` 作成
- `CONTRIBUTING.md` 作成
- アップグレードガイド `UPGRADE.md` 作成

---

## 6. パフォーマンスベンチマーク (Steps 53-60)

**現在地**: プロファイリングツール欠如、cache_manager は LRU のみ

### Step 53: ベンチマークディレクトリ作成
- `benchmark/` ディレクトリ作成
- `sample_pdfs/` サブディレクトリ作成（テスト用ダミーファイル）

### Step 54: ベンチマークランナー作成
- `benchmark/run_benchmark.py` 作成
- `time.time()` で処理時間計測
- `memory_profiler` 使用（可能なら）

### Step 55: OCR ベンチマーク追加
- ベンチマークに PDF→テキスト変換時間計測追加
- DPI 別 (150, 300, 600) での処理時間比較

### Step 56: Gemini API ベンチマーク追加
- ベンチマークに API 呼出時間計測追加
- チャンク数別処理時間比較

### Step 57: キャッシュ効果測定追加
- 同一ファイル2回目処理の時間を測定
- キャッシュヒット率を表示

### Step 58: cache_manager インクリメンタル更新対応
- `src/cache_manager.py` の `set` メソッド拡張
- 既存エントリ更新时间更新
- TTL (Time To Live) サポート追加

### Step 59: Bottleneck 分析出力追加
- ベンチマーク結果に各フェーズの内訳表示
- 最も時間がかかった処理の特定

### Step 60: レポート生成追加
- `benchmark/report.py` 作成
- ベンチマーク結果を HTML レポートで出力

---

## 7. 最終統合/リリース準備 (Steps 61-72)

**現在地**: コンポーネント連携あり、本番環境対応不完全

### Step 61: 例外階層整備
- `src/exceptions.py` に以下の例外クラス追加:
  - `TemplateNotFoundError`
  - `EncryptionError`
  - `AuditLogError`
  - `USBDeviceError`
  - `I18nTranslationError`

### Step 62: 全コンポーネント統合テスト
- `tests/test_integration.py` 作成
- PDF投入→全出力生成の(end-to-end)テスト追加

### Step 63: エラーログ集約
- `src/error_handler.py` 確認
- 全モジュールからの例外を一元管理
- エラーの段階的詳細化 (root cause → user message)

### Step 64: 設定バリデーション强化
- `config/config.py` の Config クラスに `validate()` メソッド追加
- 必須 API キーpresence check
- 数値範囲 validation

### Step 65: リソース清理確認
- `src/pdf_processor.py` の `extract_images_from_pdf` が Image オブジェクトを明示的に close しているか確認
- `cache_manager` が `_max_entries` を超えたら適切に evict しているか確認

### Step 66: スレッド安全性確認
- `orchestrator.py` の `_worker_loop` が stop_event 経由で停止するか確認
- `progress_manager.py` の `CancellationToken` が thread-safe か確認

### Step 67: WebSocket 進捗本実装
- `src/web/app.py` の `websocket_progress` を修正
- 実際の処理進捗を WebSocket 経由で送信
- テストクライアントで動作確認

### Step 68: リリースノード作成
- `RELEASE_NOTES.md` 作成
- 新機能・改善点・修正点を明記
- アップグレード注意事項記載

### Step 69: 最終動作確認
- 全テスト実行: `python -m pytest tests/ -v`
- 手動テスト: 実際のPDFでend-to-end処理
- Windows .exe で動作確認

### Step 70: 外部API 키管理整顿
- `.env.example` 作成
- `.gitignore` に `.env` 追加確認
- ドキュメントにAPIキー取得手順記載

### Step 71: Docker対応（任意）
- `Dockerfile` 作成
- `docker-compose.yml` 作成
- README に Docker 起動手順追加

### Step 72: 最終レビュー
- 全ソースコードのリント確認
- 型ヒントの統一
- docstring の整備
- LICENSE, README, CHANGELOG の最終確認

---

## 依存関係マッピング

```
Step 1-12 (USB)     : watchdog ライブラリ使用
Step 13-22 (i18n)   : 辞書データ追加のみ、依存なし
Step 23-34 (Template): ファイルI/O、JSON
Step 35-44 (Security): cryptography ライブラリ使用
Step 45-52 (Package) : setuptools, GitHub Actions
Step 53-60 (Benchmark): time, memory_profiler
Step 61-72 (統合)    : 全モジュール
```

## 優先度순

| Priority | Steps | 理由 |
|----------|-------|------|
| 1 | 23-34 (Template) | ユーザー視認性が高く、すぐに価値あり |
| 2 | 61-67 (統合) | システム安定性向上 |
| 3 | 1-12 (USB) | コア機能拡張 |
| 4 | 35-44 (Security) | プライバシー保護対応 |
| 5 | 13-22 (i18n) | 国际化対応 |
| 6 | 45-52 (Package) | 配布・導入容易化 |
| 7 | 53-60 (Benchmark) | 性能改善の基盤 |

---

*本計画は 各Stepが1-2時間以内で完了する粒度で設計されている。低性能LLMでも各Stepを順番に実装していけば最終的な完成品が得られる。*
