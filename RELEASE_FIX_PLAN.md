# リリース前修正 実装計画書

## 概要
manual_processor v2.4.0 のリリースに向けた、コードレビューで検出された課題の修正計画。

---

## 1. 必須修正（リリースブロッカー）

### 1.1 processor.py: 重複コード削除
**優先度**: Critical  
**ファイル**: `src/processor/processor.py`  
**行**: 362-382（削除対象）

**現状**: `_generate_outputs` 内で PDF/Word 生成が 2 回実行されている
- 1 回目: 362-382 行目（図表生成前）
- 2 回目: 414-438 行目（図表生成後・QRコード含む）

**修正内容**:
```python
# 362-382 行目を完全削除
# 414-438 行目（QRコード・図表含む完全版）のみ残す
```

**影響範囲**: なし（2 回目が完全版のため）
**テスト**: 既存テスト `test_processor.py` で確認

---

### 1.2 web/app.py: rendered_path 未定義バグ修正
**優先度**: Critical  
**ファイル**: `src/web/app.py`  
**行**: 476

**現状**: `save_mermaid_and_rebuild` で `rendered_path` が `if config.generate_diagram_png:` ブロック内でのみ定義される

**修正内容**:
```python
# 446-453 行目付近
rendered_path = None  # 初期化をブロック外に移動
if config.generate_diagram_png and diagram_path:
    rendered_path = diagram_gen.render_to_image(...)
    outputs["diagram"] = str(rendered_path)

# 476 行目では rendered_path が確実に定義済み
create_formatted_pdf(..., diagram_path=rendered_path)
```

**影響範囲**: Mermaid 保存・再生成エンドポイント
**テスト**: `test_web_app.py::TestMermaidEndpoints` で確認

---

## 2. 推奨改善（品質向上）

### 2.1 セキュリティ: Bandit Low 件数の抑制
**優先度**: High  
**対象ファイルと行**:

| ファイル | 行 | 種別 | 対処 |
|---------|-----|------|------|
| `diagram_generator.py` | 96-101 | subprocess 部分パス | `shutil.which("mmdc")` でフルパス取得 + `# nosec B607,B603` |
| `diagram_generator.py` | 136-137 | try-except-continue | `# nosec B112` |
| `gui/main.py` | 228-231 | subprocess (explorer) | `os.startfile()` 等の代替 + `# nosec B603` |
| `gui/main.py` | 424-425 | try-except-pass | ログ出力追加 + `# nosec B110` |
| `pdf_processor.py` | 52-53 | try-except-pass | `# nosec B110` |
| `processor/processor.py` | 251-252 | try-except-pass | `# nosec B110` |
| `security_manager.py` | 298-299 | try-except-pass | `# nosec B110` |
| `security_manager.py` | 374-375 | try-except-continue | `# nosec B112` |
| `usb_monitor.py` | 100-101 | try-except-pass | `# nosec B110` |

**作業時間**: 30 分
**検証**: `make security` で Bandit 警告 0 件確認

---

### 2.2 設定: デッドコード除去
**優先度**: Medium  
**ファイル**: `config/config.py`  
**行**: 233-238

**現状**:
```python
@property
def google_api_key(self) -> str:
    return ""

@property
def gemini_api_key(self) -> str:
    return ""
```

**修正案 A**: プロパティ削除（参照箇所なしの場合）
**修正案 B**: 環境変数から取得する実装に変更

**調査必要**: `grep -r "google_api_key\|gemini_api_key" src/` で参照確認

---

### 2.3 Web アプリ: グローバルキャッシュのスレッドセーフ化
**優先度**: High（本番運用時必須）  
**ファイル**: `src/web/app.py`  
**行**: 182, 241

**現状**:
```python
UPLOADED_FILES: Dict[str, Dict[str, Any]] = {}
PROCESSING_RESULTS: Dict[str, Dict[str, Any]] = {}
```

**修正内容**:
```python
import threading

UPLOADED_FILES: Dict[str, Dict[str, Any]] = {}
UPLOADED_FILES_LOCK = threading.RLock()

PROCESSING_RESULTS: Dict[str, Dict[str, Any]] = {}
PROCESSING_RESULTS_LOCK = threading.RLock()

# 使用時は with lock:
with UPLOADED_FILES_LOCK:
    UPLOADED_FILES[file_id] = meta
```

**代替案**: `asyncio.Lock` 使用（FastAPI 非同期コンテキストの場合）

---

### 2.4 暗号化: キー生成ロジック修正
**優先度**: High  
**ファイル**: `src/security_manager.py`  
**行**: 237, 261

**現状**: `Fernet.generate_key()` を毎回呼んでいるため、暗号化・復号でキーが異なる

**修正内容**:
```python
@classmethod
def _get_or_create_fernet(cls) -> Optional[Fernet]:
    """Fernet インスタンスを取得（キーはキャッシュ）"""
    if not hasattr(cls, '_fernet_cache'):
        cls._fernet_cache = None
    
    if cls._fernet_cache is not None:
        return cls._fernet_cache
    
    if not _HAS_CRYPTO:
        return None
    
    key = cls._get_encryption_key()
    if not key:
        return None
    
    try:
        cls._fernet_cache = Fernet(key)
        return cls._fernet_cache
    except Exception:
        return None

@classmethod
def encrypt_data(cls, data: bytes) -> Tuple[bytes, bool]:
    f = cls._get_or_create_fernet()
    if not f:
        return data, False
    try:
        return f.encrypt(data), True
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return data, False

@classmethod
def decrypt_data(cls, encrypted_data: bytes) -> Tuple[bytes, bool]:
    f = cls._get_or_create_fernet()
    if not f:
        return encrypted_data, False
    try:
        return f.decrypt(encrypted_data), True
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return encrypted_data, False
```

---

### 2.5 fpdf2 非推奨警告修正
**優先度**: Medium  
**ファイル**: `src/pdf_generator.py`  
**行**: 157, 255, 276

**修正内容**:
```python
# 旧
pdf.cell(0, 6, "text", ln=True, align="C")

# 新
from fpdf.enums import XPos, YPos
pdf.cell(0, 6, "text", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
```

**影響**: 3 箇所すべて修正
**検証**: `pytest tests/test_pdf_generator.py -v` で警告消失確認

---

### 2.6 型ヒント追加
**優先度**: Low（継続的改善）  
**対象**: `src/` 配下の主要関数

**方針**: 新規コード・修正箇所で必須化。既存は段階的追加。

---

### 2.7 ハードコード値の設定化
**優先度**: Low  
**ファイル**: `src/processor/processor.py`  
**行**: 237, 259

**現状**:
```python
batch_size = 4
max_workers = min(len(batch), 4)
```

**修正**: `Config` に `ocr_batch_size`, `ocr_max_workers` 追加

---

## 3. 軽微な磨き込み

### 3.1 nosec コメント一括追加
**対象**: 2.1 で特定した 9 箇所

### 3.2 diagram_generator.py: mmdc パス解決
```python
import shutil
mmdc_path = shutil.which("mmdc")
if not mmdc_path:
    raise RuntimeError("mmdc (Mermaid CLI) not found in PATH")
result = subprocess.run([mmdc_path, ...], ...)
```

### 3.3 pyproject.toml: Ruff 設定追加
```toml
[tool.ruff]
line-length = 127
target-version = "py38"
select = ["E", "F", "W", "I", "N", "UP", "B", "C4", "SIM", "T10"]
ignore = ["E501", "B008"]
exclude = ["tests/fixtures", "temp", "dist", "build"]

[tool.ruff.per-file-ignores]
"src/security_manager.py" = ["B105", "B106"]  # キーリング用途は許容
```

---

## 4. 実装スケジュール

| フェーズ | 作業 | 所要時間 | 依存 |
|---------|------|---------|------|
| **Phase 1** | 必須修正 1.1, 1.2 | 15 分 | なし |
| **Phase 2** | セキュリティ 2.1, 2.5 | 45 分 | Phase 1 |
| **Phase 3** | 暗号化 2.4, キャッシュ 2.3 | 30 分 | Phase 1 |
| **Phase 4** | 設定 2.2, ハードコード 2.7 | 20 分 | なし |
| **Phase 5** | 型ヒント 2.6, Ruff 3.3, mmdc 3.2 | 60 分 | 任意 |
| **総計** | | **~2.5 時間** | |

---

## 5. 検証手順

### 5.1 必須テスト実行
```bash
# 全テスト
make test
# または
python -m pytest tests/ -v

# カバレッジ確認
make coverage-check
```

### 5.2 セキュリティスキャン
```bash
make security
# Bandit 警告 0 件を確認
```

### 5.3 手動動作確認
```bash
# CLI モード
python main.py --cli --input test.pdf

# Web UI
python -m uvicorn src.web.app:app --reload
# ブラウザで http://localhost:8000
# Mermaid 編集・保存フロー確認
```

---

## 6. リスクと対策

| リスク | 影響 | 対策 |
|--------|------|------|
| 暗号化キー変更で既存データ復号不可 | High | 移行スクリプト作成、または現行キー互換維持 |
| グローバルキャッシュロックで性能低下 | Low | `RLock` 使用、必要なら `asyncio.Lock` へ移行 |
| fpdf2 API 変更でレイアウト崩れ | Medium | 視覚確認テスト追加、スナップショットテスト検討 |

---

## 7. 完了定義

- [ ] 必須修正 2 件完了
- [ ] `make test` 全件パス（1121 passed）
- [ ] `make coverage-check` 85% 以上維持
- [ ] `make security` Bandit 警告 0 件
- [ ] 手動動作確認（CLI/Web/Mermaid 編集）OK
- [ ] CHANGELOG.md 更新

---

## 8. メモ

- Phase 1-3 までで「リリース可能」状態達成見込み
- Phase 4-5 は次バージョン（v2.5.0）に持ち越し可
- 暗号化修正（2.4）は既存データ互換性に注意。必要なら移行期間設ける