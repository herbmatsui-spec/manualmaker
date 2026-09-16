# セキュリティ・品質改善 実装計画書

## 概要
コードレビューで検出された問題に対応するための詳細実装計画。優先度順にタスクを整理し、各タスクの実装手順、影響範囲、テスト戦略を定義する。

---

## 1. タスク一覧と優先度

| ID | 優先度 | タイトル | 影響範囲 | 推定工数 |
|----|--------|----------|----------|----------|
| T-01 | **Critical** | パストラバーサル脆弱性修正 | `src/web/app.py` (upload) | 2h |
| T-02 | **Critical** | グローバル設定変更の排除 | `src/web/app.py` (process), `config/config.py` | 4h |
| T-03 | **High** | 情報漏洩対策（絶対パス露出） | `src/web/app.py` (upload) | 1h |
| T-04 | **High** | インメモリストレージの外部化設計 | `src/web/app.py` (UPLOADED_FILES, PROCESSING_RESULTS) | 8h |
| T-05 | **Medium** | ファイル名バリデーション強化 | `src/web/app.py` (upload) | 1h |
| T-06 | **Medium** | 設定のイミュータブル化 / リクエストスコープ化 | `config/config.py`, `src/web/app.py` | 4h |
| T-07 | **Low** | セキュリティマネージャの Fernet キャッシュ修正 | `src/security_manager.py` | 1h |
| T-08 | **Low** | 包括的テスト追加・回帰テスト実行 | 全体 | 4h |

---

## 2. 詳細タスク仕様

### T-01: パストラバーサル脆弱性修正（Critical）

#### 現状の問題
```python
# src/web/app.py:190-220
save_dir = config.temp_directory / file_id
save_dir.mkdir(parents=True, exist_ok=True)
file_path = save_dir / file.filename  # 危険: file.filename が "../../../etc/passwd" 等の可能性
```

#### 修正内容
1. ファイル名からベース名のみを抽出
2. 危険文字の除外・検証
3. パスが `save_dir` 配下に収まることを保証

#### 実装手順
```python
# src/web/app.py - upload_file 関数内
import re
from pathlib import Path

def sanitize_filename(filename: str) -> str:
    """ファイル名をサニタイズし、ベース名のみを返す"""
    # パス区切り文字と制御文字を除去
    name = Path(filename).name  # ディレクトリ部分を除去
    name = re.sub(r'[\x00-\x1f\x7f]', '', name)  # 制御文字除去
    name = re.sub(r'[\\/:*?"<>|]', '_', name)    # Windows禁止文字置換
    # 長さ制限
    if len(name) > 255:
        stem, suffix = Path(name).stem, Path(name).suffix
        name = stem[:255 - len(suffix)] + suffix
    return name

# 使用例
safe_name = sanitize_filename(file.filename)
file_path = save_dir / safe_name

# 追加の安全性チェック: 解決後のパスが save_dir 配下か確認
try:
    file_path.resolve().relative_to(save_dir.resolve())
except ValueError:
    raise HTTPException(status_code=400, detail="無効なファイル名です")
```

#### 影響範囲
- `src/web/app.py` のみ
- 既存テスト: `tests/test_web_upload.py` にパストラバーサル試行テストを追加

#### 受け入れ基準
- [ ] `../../../etc/passwd` 等のファイル名でアップロードしても `save_dir` 外に書き出されない
- [ ] 正常なファイル名（日本語、スペース、記号含む）でアップロード成功
- [ ] 既存の統合テストが全てパス

---

### T-02: グローバル設定変更の排除（Critical）

#### 現状の問題
```python
# src/web/app.py:253-260
if options.prompt_layout in {"horizontal", "vertical"}:
    config.prompt_layout = options.prompt_layout  # グローバル変更！
if options.prompt_strict_mode is not None:
    config.prompt_strict_mode = options.prompt_strict_mode
# ...
processor = DocumentProcessor(config)  # 汚染された config を渡す
```

#### 修正方針
**方針 A: リクエストごとに設定のコピーを作成（推奨・低リスク）**
```python
# config/config.py にコピーメソッド追加
class AppConfig:
    def copy_with_overrides(self, **overrides) -> 'AppConfig':
        """現在の設定をコピーし、指定された属性を上書きした新インスタンスを返す"""
        new_settings = self._settings.model_copy(deep=True)
        for key, value in overrides.items():
            if hasattr(new_settings, key):
                setattr(new_settings, key, value)
        return AppConfig(settings=new_settings)
```

```python
# src/web/app.py: process_pdf_api 内
override = {}
if options.prompt_layout in {"horizontal", "vertical"}:
    override["prompt_layout"] = options.prompt_layout
if options.prompt_strict_mode is not None:
    override["prompt_strict_mode"] = options.prompt_strict_mode
# ...

request_config = config.copy_with_overrides(**override)
processor = DocumentProcessor(request_config)
```

**方針 B: DocumentProcessor にオプション引数を追加（よりクリーン）**
```python
# src/processor/processor.py
def process_pdf(self, pdf_path: Path, compact_layout: bool = False, use_emojis: bool = False,
                prompt_layout: Optional[str] = None, prompt_strict_mode: Optional[bool] = None,
                prompt_has_diagrams: Optional[bool] = None, prompt_low_quality_mode: Optional[bool] = None,
                progress_tracker = None, cancel_token = None,
                file_id: Optional[str] = None, base_url: str = "http://localhost:8000") -> Dict:
    # 内部で self.config の値をオプションで上書きして使用
```

#### 推奨: 方針 A + 方針 B の併用
- 設定コピーメソッドを実装し、プロセッサにはコピー済み config を渡す
- 将来的にはプロセッサ側でオプション引数を受け取れるように拡張

#### 実装手順
1. `config/config.py` に `copy_with_overrides()` メソッド追加
2. `src/web/app.py` の `process_pdf_api` を修正し、コピー済み config を使用
3. `DocumentProcessor` が参照する設定値をローカル変数で上書き可能にする（オプション引数追加）

#### 影響範囲
- `config/config.py`
- `src/web/app.py`
- `src/processor/processor.py` (オプション引数追加の場合)

#### 受け入れ基準
- [ ] 並列リクエストで異なるオプションを指定しても互いに影響しない
- [ ] 既存の単体テスト・統合テストが全てパス
- [ ] 設定変更後の `/api/config` エンドポイントが元の設定を返す（グローバル未変更）

---

### T-03: 情報漏洩対策（High）

#### 現状の問題
```python
# src/web/app.py:222-230
meta = {
    "file_id": file_id,
    "filename": file.filename,
    "size_mb": round(size_mb, 2),
    "path": str(file_path)  # 絶対パスが露出
}
```

#### 修正内容
- `path` フィールドを削除、または相対パス（`file_id/filename` 形式）のみ返す

#### 実装手順
```python
meta = {
    "file_id": file_id,
    "filename": safe_name,  # サニタイズ済み
    "size_mb": round(size_mb, 2),
    "relative_path": f"{file_id}/{safe_name}"
}
```

#### 受け入れ基準
- [ ] レスポンスに絶対パスが含まれない
- [ ] フロントエンドが `relative_path` を使用してダウンロード等を行える

---

### T-04: インメモリストレージの外部化設計（High）

#### 現状の問題
```python
# src/web/app.py:181-185
UPLOADED_FILES: Dict[str, Dict[str, Any]] = {}
PROCESSING_RESULTS: Dict[str, Dict[str, Any]] = {}
```
マルチワーカー環境でデータが共有されない。

#### 設計案
**Phase 1: インターフェース抽象化（即時対応）**
```python
# src/web/storage.py (新規)
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class FileStorage(ABC):
    @abstractmethod
    def save_upload(self, file_id: str, meta: Dict[str, Any]) -> None: ...
    @abstractmethod
    def get_upload(self, file_id: str) -> Optional[Dict[str, Any]]: ...
    @abstractmethod
    def list_uploads(self) -> list: ...
    @abstractmethod
    def save_result(self, file_id: str, result: Dict[str, Any]) -> None: ...
    @abstractmethod
    def get_result(self, file_id: str) -> Optional[Dict[str, Any]]: ...
    @abstractmethod
    def delete(self, file_id: str) -> None: ...

class InMemoryStorage(FileStorage):
    """既存の辞書ベース実装（開発・単体テスト用）"""
    ...

class RedisStorage(FileStorage):
    """Redis ベース実装（本番用）"""
    ...
```

**Phase 2: 設定による切り替え**
```python
# config/settings.py に storage.backend 追加
# src/web/app.py で DI
storage: FileStorage = RedisStorage() if config.storage_backend == "redis" else InMemoryStorage()
```

#### 実装手順
1. `src/web/storage.py` 新規作成、インターフェースと実装を定義
2. `src/web/app.py` でグローバル辞書を `storage` インスタンスに置換
3. 設定ファイル (`config/settings.py`) に `storage_backend` 追加
4. `RedisStorage` 実装（redis-py 依存追加）

#### 受け入れ基準
- [ ] 開発環境では `InMemoryStorage` で従来通り動作
- [ ] 本番環境で `RedisStorage` に切り替え可能
- [ ] 複数ワーカーでアップロード・処理結果が共有される

---

### T-05: ファイル名バリデーション強化（Medium）

#### 実装内容
T-01 の `sanitize_filename()` に以下を追加:
- NULL バイト (`\x00`) 拒否
- ファイル名長上限 (255 文字) チェック
- 予約語チェック (Windows: CON, PRN, AUX, NUL 等)
- 拡張子が `.pdf` であることの再確認

#### 受け入れ基準
- [ ] 悪意のあるファイル名で 400 エラーが返る
- [ ] 正常な PDF ファイル名でアップロード成功

---

### T-06: 設定のイミュータブル化 / リクエストスコープ化（Medium）

#### 現状
`AppConfig` の setter が `_settings` を直接変更する。

#### 修正方針
1. **即時対策**: setter を削除し、読み取り専用プロパティのみにする
2. **根本対策**: Pydantic Settings の `model_copy()` を活用し、リクエストごとに新インスタンスを生成

```python
# config/config.py
class AppConfig:
    # setter を全て削除
    @property
    def prompt_layout(self) -> str:
        return self._settings.prompt.layout
    # setter なし
    
    def with_overrides(self, **kwargs) -> 'AppConfig':
        """オーバーライド適用済みの新インスタンスを返す"""
        new_settings = self._settings.model_copy(deep=True)
        for key, value in kwargs.items():
            # ネストされた属性への対応 (prompt.layout 等)
            parts = key.split('.')
            obj = new_settings
            for part in parts[:-1]:
                obj = getattr(obj, part)
            setattr(obj, parts[-1], value)
        return AppConfig(settings=new_settings)
```

#### 影響範囲
- `config/config.py`
- 設定を書き換えていた全箇所 (`src/web/app.py`, `src/gui/`, `src/orchestrator.py` 等)

#### 受け入れ基準
- [ ] 既存コードで setter を呼んでいる箇所がコンパイルエラーまたは実行時エラーにならないよう移行済み
- [ ] リクエストごとの設定分離が機能する

---

### T-07: セキュリティマネージャの Fernet キャッシュ修正（Low）

#### 現状
```python
# src/security_manager.py:266-290
@classmethod
def _get_or_create_fernet(cls) -> Optional[Fernet]:
    if not hasattr(cls, '_fernet_cache'):
        cls._fernet_cache = None
    if cls._fernet_cache is not None:
        return cls._fernet_cache
    # ... キー取得と Fernet 作成 ...
    cls._fernet_cache = Fernet(key)
    return cls._fernet_cache
```
環境変数 `ENCRYPTION_KEY` 変更時にキャッシュが更新されない。

#### 修正内容
キーのハッシュをキャッシュキーとして使用、または毎回新規作成（パフォーマンス影響微小）。

```python
@classmethod
def _get_or_create_fernet(cls) -> Optional[Fernet]:
    key = cls._get_encryption_key()
    if not key:
        return None
    # キーのハッシュでキャッシュ管理
    key_hash = hashlib.sha256(key).hexdigest()
    if not hasattr(cls, '_fernet_cache'):
        cls._fernet_cache = {}
    if key_hash in cls._fernet_cache:
        return cls._fernet_cache[key_hash]
    cls._fernet_cache[key_hash] = Fernet(key)
    return cls._fernet_cache[key_hash]
```

#### 受け入れ基準
- [ ] 環境変数変更後に再暗号化・復号が正常動作
- [ ] 既存の暗号化テストがパス

---

### T-08: 包括的テスト追加・回帰テスト実行（Low）

#### テスト追加項目
| テスト種別 | 対象 | 内容 |
|------------|------|------|
| セキュリティテスト | `test_security_path_traversal.py` | パストラバーサル試行、危険ファイル名拒否 |
| 並行テスト | `test_concurrent_config.py` | 並列リクエストで設定が分離されること |
| 統合テスト | `test_upload_download_flow.py` | アップロード→処理→ダウンロードの一連フロー |
| 負荷テスト | `locustfile.py` | 複数ワーカーでのストレージ共有確認 |

#### 実行コマンド
```bash
cd manual_processor
# 既存テスト全実行
python -m pytest tests/ -v --tb=short

# 新規セキュリティテスト
python -m pytest tests/test_security_*.py -v

# カバレッジ確認
python -m pytest tests/ --cov=src --cov=config --cov-fail-under=90
```

#### 受け入れ基準
- [ ] 全テストパス (1325 件以上)
- [ ] カバレッジ 90% 維持
- [ ] 新規セキュリティテストが CI で自動実行される

---

## 3. 実装スケジュール（目安）

| 週 | 実施タスク | マイルストーン |
|----|------------|----------------|
| 1週目 | T-01, T-03, T-05 | Critical/High セキュリティ修正完了 |
| 2週目 | T-02, T-06 | 設定変更排除・イミュータブル化完了 |
| 3週目 | T-04 (Phase 1) | ストレージインターフェース抽象化完了 |
| 4週目 | T-04 (Phase 2), T-07 | Redis 対応・細部修正完了 |
| 5週目 | T-08 | テスト追加・全テストパス・ドキュメント更新 |

---

## 4. リスクと対策

| リスク | 影響度 | 対策 |
|--------|--------|------|
| 既存機能への回帰 | 高 | 充実したテストスイートでカバー、段階的リリース |
| 設定コピーによるメモリ増加 | 低 | 設定オブジェクトは小さいため無視可能 |
| Redis 導入の運用コスト | 中 | 開発環境は InMemory のまま、本番のみ Redis |
| フロントエンド互換性 | 低 | API レスポンス形式変更は `relative_path` 追加のみ、既存 `path` は非推奨化 |

---

## 5. デプロイ手順

1. **ステージング環境へデプロイ**
   - 全テスト実行・パス確認
   - セキュリティスキャン (bandit, safety) 実行
   - 負荷テストで並行処理確認

2. **本番環境へデプロイ**
   - Blue/Green デプロイで無停止リリース
   - Redis インスタンス準備・接続確認
   - 監視アラート設定 (エラー率、レスポンス時間)

3. **ロールバック計画**
   - 設定変更 (T-02, T-06) は機能フラグで無効化可能にする
   - ストレージバックエンドは環境変数で即座に切り替え可能

---

## 6. 関連ファイル一覧

### 修正対象ファイル
- `src/web/app.py` - T-01, T-02, T-03, T-04, T-05
- `config/config.py` - T-02, T-06
- `src/processor/processor.py` - T-02 (オプション引数追加時)
- `src/security_manager.py` - T-07
- `config/settings.py` - T-04, T-06 (設定項目追加)

### 新規作成ファイル
- `src/web/storage.py` - T-04
- `tests/test_security_path_traversal.py` - T-08
- `tests/test_concurrent_config.py` - T-08

### 設定ファイル
- `manual_processor/.env.example` - 新規設定項目追加例
- `wrangler.toml` - Cloudflare Workers 環境変数対応確認

---

## 7. 完了の定義

- [ ] 全 Critical/High タスクが実装・テスト済み
- [ ] 既存テスト 100% パス
- [ ] 新規セキュリティテスト追加・パス
- [ ] ステージング環境で動作確認済み
- [ ] ドキュメント (README, SECURITY.md) 更新済み
- [ ] CHANGELOG.md に修正内容記載

---

## 付録: 修正前後のコード比較例

### T-01 修正前後
```python
# Before
file_path = save_dir / file.filename

# After
safe_name = sanitize_filename(file.filename)
file_path = save_dir / safe_name
file_path.resolve().relative_to(save_dir.resolve())  # 検証
```

### T-02 修正前後
```python
# Before (グローバル汚染)
config.prompt_layout = options.prompt_layout
processor = DocumentProcessor(config)

# After (リクエストスコープ)
request_config = config.copy_with_overrides(
    prompt_layout=options.prompt_layout,
    prompt_strict_mode=options.prompt_strict_mode,
)
processor = DocumentProcessor(request_config)
```

---

*作成日: 2026-09-14*  
*作成者: Kilo Code Review Agent*  
*バージョン: 1.0*