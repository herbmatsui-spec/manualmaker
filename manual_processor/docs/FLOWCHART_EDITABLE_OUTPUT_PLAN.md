# フローチャート編集可能出力 実装計画書

## 概要

現状のフローチャート出力は PNG 画像のみである。本計画では、Mermaid コードを編集可能なファイル形式（Markdown `.md`、Mermaid `.mmd`）でも出力可能にする拡張を実施する。

| 項目 | 内容 |
|------|------|
| 対象ファイル | `diagram_generator.py`, `output_manager.py`, `processor.py`, `web/app.py`, `config` |
| 新規ファイル | なし（既存モジュール拡張のみ） |
| テスト追加 | `tests/test_diagram_generator.py` 拡張 |
| ステップ数 | 15ステップ + 5回の検証 |
| 推定工数 | 約1日 |

## 設計原則

- 既存 `DiagramResult.mermaid_code` を流用し、新規生成ロジックは追加しない
- `DiagramResult` に画像パスと同様に `.md` / `.mmd` パスを持たせる
- 各ステップは **1コミット = 1〜3ステップ** 単位で実装
- 3ステップごとに検証を実施
- 既存テストを破壊しない

---

## ステップ 1: `DiagramResult` に編集可能出力パスを追加

**目的**: データモデルを拡張し、`.md` / `.mmd` の出力パスを保持できるようにする。

**実装内容**:
1. `src/diagram_generator.py` の `DiagramResult` に以下を追加:
   - `markdown_path: Optional[Path]` - Markdown ファイルパス
   - `mermaid_path: Optional[Path]` - Mermaid ファイルパス

**ファイル**: `/workspaces/manualmaker/manual_processor/src/diagram_generator.py`

**検証**:
```bash
python -c "from src.diagram_generator import DiagramResult; r = DiagramResult('', None, '', True); print(hasattr(r, 'markdown_path'), hasattr(r, 'mermaid_path'))"
```

---

## ステップ 2: Markdown (`.md`) 保存ユーティリティを実装

**目的**: Mermaid コードを Markdown 形式で保存する関数を追加する。

**実装内容**:
1. `DiagramGenerator` に以下を追加:
   ```python
   def save_as_markdown(self, mermaid_code: str, output_path: Path, title: str = "フローチャート") -> Path
   ```
2. フォーマット:
   ```markdown
   # フローチャート: {title}

   ```mermaid
   {mermaid_code}
   ```
   ```

**ファイル**: `/workspaces/manualmaker/manual_processor/src/diagram_generator.py`

**検証**:
```bash
python -c "
from pathlib import Path
from src.diagram_generator import DiagramGenerator
gen = DiagramGenerator.__new__(DiagramGenerator)
p = Path('/tmp/test.md')
r = gen.save_as_markdown('flowchart TD\nA-->B', p, 'Test')
print(r.exists(), r.read_text())
"
```

---

## ステップ 3: Mermaid (`.mmd`) 保存ユーティリティを実装

**目的**: Mermaid コードを生の `.mmd` 形式で保存する関数を追加する。

**実装内容**:
1. `DiagramGenerator` に以下を追加:
   ```python
   def save_as_mermaid(self, mermaid_code: str, output_path: Path) -> Path
   ```
2. 内容は `mermaid_code` をそのまま書き込む

**ファイル**: `/workspaces/manualmaker/manual_processor/src/diagram_generator.py`

**検証**:
```bash
python -c "
from pathlib import Path
from src.diagram_generator import DiagramGenerator
gen = DiagramGenerator.__new__(DiagramGenerator)
p = Path('/tmp/test.mmd')
r = gen.save_as_mermaid('flowchart TD\nA-->B', p)
print(r.exists(), r.read_text())
"
```

---

## 🔍 検証 1: `diagram_generator.py` のユニットテスト

**目的**: 新規追加したユーティリティのテストを実施する。

**実行コマンド**:
```bash
cd /workspaces/manualmaker/manual_processor
pytest tests/test_diagram_generator.py -v
```

**期待結果**:
- 既存テストが全て PASS
- 新規テストも PASS

---

## ステップ 4: `DiagramGenerator.generate()` を拡張し `.md` / `.mmd` を保存

**目的**: フローチャート生成成功時に、画像と並行して `.md` / `.mmd` も保存する。

**実装内容**:
1. `DiagramGenerator.generate()` のシグネチャに以下を追加:
   - `markdown_path: Optional[Path] = None`
   - `mermaid_path: Optional[Path] = None`
   - `output_path: Optional[Path] = None`（PNG をオプション化）
2. レンダリング成功後、またはフォールバック成功後、対応するパスが渡されていれば保存を実行
3. `DiagramResult` に保存結果を反映

**ファイル**: `/workspaces/manualmaker/manual_processor/src/diagram_generator.py`

**検証**:
```bash
python -c "
from pathlib import Path
from src.diagram_generator import DiagramGenerator
gen = DiagramGenerator.__new__(DiagramGenerator)
gen.generate_mermaid_code = lambda *a, **k: 'flowchart TD\nA-->B'
gen.validate_mermaid_code = lambda code: (True, '')
gen.render_to_image = lambda *a, **k: Path('/tmp/test.png')
r = gen.generate('text', [], [], output_path=Path('/tmp/out.png'), markdown_path=Path('/tmp/out.md'), mermaid_path=Path('/tmp/out.mmd'))
print(r.markdown_path.exists(), r.mermaid_path.exists())
"
```

---

## ステップ 5: `output_manager.py` に `.md` / `.mmd` 保存処理を追加

**目的**: 出力管理レイヤーで `.md` / `.mmd` を一括保存する。

**実装内容**:
1. `OutputFiles` データクラスに以下を追加:
   - `diagram_markdown_path: Path`
   - `diagram_mermaid_path: Path`
2. `OutputConfig` に以下を追加:
   - `include_diagram_markdown: bool = True`
   - `include_diagram_mermaid: bool = True`
3. `save_all_formats()` / `save_single_format()` 内で、フローチャート保存後に `.md` / `.mmd` 保存を呼び出す

**ファイル**: `/workspaces/manualmaker/manual_processor/src/output_manager.py`

**検証**:
```bash
python -c "
from pathlib import Path
from src.output_manager import OutputConfig
c = OutputConfig(output_directory=Path('/tmp'), base_name='test', include_pdf=False, include_docx=False, include_audio=False)
print(c.include_diagram_markdown, c.include_diagram_mermaid)
"
```

---

## ステップ 6: `OutputFiles` の既存テスト確認

**目的**: `output_manager.py` の変更が既存テストに影響しないことを確認する。

**実行コマンド**:
```bash
cd /workspaces/manualmaker/manual_processor
pytest tests/ -k output -v
```

**期待結果**:
- 既存の output_manager 関連テストが PASS
- 新規フィールド追加による破壊的変更がない

---

## 🔍 検証 2: `output_manager` 関連テストの実行

**目的**: ステップ 4-6 の変更が既存テストに影響しないことを確認する。

**実行コマンド**:
```bash
cd /workspaces/manualmaker/manual_processor
pytest tests/test_diagram_generator.py tests/test_web_api.py -v
```

**期待結果**:
- 全テスト PASS

---

## ステップ 7: `processor.py` の `_generate_outputs()` を拡張

**目的**: フローチャート生成結果から `.md` / `.mmd` を保存する。

**実装内容**:
1. `_generate_outputs()` 内で `DiagramResult` から `markdown_path` / `mermaid_path` を取得
2. 保存処理を呼び出し、`outputs` 辞書にキーを追加:
   - `"diagram_markdown"` -> `.md` パス
   - `"diagram_mermaid"` -> `.mmd` パス

**ファイル**: `/workspaces/manualmaker/manual_processor/src/processor/processor.py`

**検証**:
```bash
python -c "
import ast, inspect
from src.processor.processor import DocumentProcessor
src = inspect.getsource(DocumentProcessor._generate_outputs)
assert 'diagram_markdown' in src or 'diagram_mermaid' in src
print('OK')
"
```

---

## ステップ 8: `save_all_formats()` / `save_single_format()` に `.md` / `.mmd` 保存分岐を追加

**目的**: `output_manager.py` から `DiagramGenerator` の新規保存関数を呼び出す。

**実装内容**:
1. `save_single_format()` に `format_type == 'diagram_markdown'` と `format_type == 'diagram_mermaid'` を追加
2. `save_all_formats()` では `config.include_diagram_markdown/mermaid` を確認して保存

**ファイル**: `/workspaces/manualmaker/manual_processor/src/output_manager.py`

**検証**:
```bash
python -c "
from src.output_manager import save_single_format
import inspect
src = inspect.getsource(save_single_format)
assert 'diagram_markdown' in src and 'diagram_mermaid' in src
print('OK')
"
```

---

## ステップ 9: `OutputFiles` データクラスの新規フィールド確認

**目的**: データモデルが正しく拡張されていることを確認する。

**実行コマンド**:
```bash
python -c "
from src.output_manager import OutputFiles
import inspect
sig = inspect.signature(OutputFiles)
assert 'diagram_markdown_path' in str(sig)
assert 'diagram_mermaid_path' in str(sig)
print('OK')
"
```

---

## 🔍 検証 3: `processor.py` + `output_manager.py` 統合テスト

**目的**: ステップ 7-9 の変更で `processor.py` が正常に動作することを確認する。

**実行コマンド**:
```bash
cd /workspaces/manualmaker/manual_processor
pytest tests/test_processor_partial_failure.py tests/test_orchestrator_mock.py -v
```

**期待結果**:
- 全テスト PASS

---

## ステップ 10: Web API ダウンロードに `.md` / `.mmd` を追加

**目的**: フローチャートの編集可能ファイルを Web からダウンロード可能にする。

**実装内容**:
1. `src/web/app.py` の `download_file_api()` の `media_types` に以下を追加:
   - `"diagram_markdown": "text/markdown"`
   - `"diagram_mermaid": "text/plain"` (Mermaid はプレーンテキストとして配信)

**ファイル**: `/workspaces/manualmaker/manual_processor/src/web/app.py`

**検証**:
```bash
python -c "
from src.web.app import app
client = type('C', (), {'get': lambda self, p: None})()
from fastapi.testclient import TestClient
c = TestClient(app)
print('app loaded')
"
```

---

## ステップ 11: `save_mermaid_and_rebuild()` に `.md` / `.mmd` 保存を追加

**目的**: Mermaid コードを保存する API で、画像再生成と同時に `.md` / `.mmd` も保存する。

**実装内容**:
1. `save_mermaid_and_rebuild()` 内で、PNG レンダリング成功後:
   - `DiagramGenerator.save_as_markdown()` を呼び出し
   - `DiagramGenerator.save_as_mermaid()` を呼び出し
2. `outputs` 辞書に `"diagram_markdown"` / `"diagram_mermaid"` を追加

**ファイル**: `/workspaces/manualmaker/manual_processor/src/web/app.py`

**検証**:
```bash
python -c "
import inspect
from src.web.app import save_mermaid_and_rebuild
src = inspect.getsource(save_mermaid_and_rebuild)
assert 'diagram_markdown' in src
print('OK')
"
```

---

## ステップ 12: ダウンロード API のテスト追加

**目的**: Web API が `.md` / `.mmd` を正しく配信することをテストする。

**実装内容**:
1. `tests/test_web_api.py` に以下を追加:
   - `test_download_diagram_markdown`
   - `test_download_diagram_mermaid`

**ファイル**: `/workspaces/manualmaker/manual_processor/tests/test_web_api.py`

**検証**:
```bash
cd /workspaces/manualmaker/manual_processor
pytest tests/test_web_api.py -v
```

---

## 🔍 検証 4: Web API テストの実行

**目的**: Web API の新規エンドポイントが正しく動作することを確認する。

**実行コマンド**:
```bash
cd /workspaces/manualmaker/manual_processor
pytest tests/test_web_api.py -v
```

**期待結果**:
- 全テスト PASS

---

## ステップ 13: 設定に編集可能出力フラグを追加

**目的**: `.md` を標準ダウンロードとし、`.png` と `.mmd` をオプション化する。

**実装内容**:
1. `config/settings.py` の `PromptSettings` に以下を追加:
   - `generate_diagram_png: bool = True`
   - `generate_diagram_markdown: bool = True`
   - `generate_diagram_mermaid: bool = False`
2. `config/config_new.py` にプロパティを追加:
   - `generate_diagram_png`
   - `generate_diagram_markdown`
   - `generate_diagram_mermaid`

**ファイル**:
- `/workspaces/manualmaker/manual_processor/config/settings.py`
- `/workspaces/manualmaker/manual_processor/config/config_new.py`

**検証**:
```bash
python -c "
from config.config import Config
c = Config.get_instance()
print(c.generate_diagram_png, c.generate_diagram_markdown, c.generate_diagram_mermaid)
"
```

---

## ステップ 14: README.md を更新

**目的**: 新規出力形式についてユーザーに周知する。

**実装内容**:
1. `README.md` の「マルチフォーマット出力」セクションに `.md` / `.mmd` を追加

**ファイル**: `/workspaces/manualmaker/manual_processor/README.md`

**検証**:
```bash
grep -E '\\.md|\\.mmd' README.md
```

---

## ステップ 15: 最終統合テストの実行

**目的**: 全変更が既存テストと共存することを確認する。

**実行コマンド**:
```bash
cd /workspaces/manualmaker/manual_processor
pytest tests/ -v
```

**期待結果**:
- 全テスト PASS（既存99件 + 新規テスト）

---

## 🔍 検証 5: 全体テストスイートの実行

**目的**: プロジェクト全体の健全性を確認する。

**実行コマンド**:
```bash
cd /workspaces/manualmaker/manual_processor
pytest tests/ -v --tb=short
```

**期待結果**:
- 全テスト PASS
- 新規フィールド追加による破壊的変更がない

---

## 変更ファイル一覧

| ファイル | 変更種別 | 内容 |
|---------|---------|------|
| `src/diagram_generator.py` | 編集 | `DiagramResult` 拡張、`.md`/`.mmd` 保存関数追加 |
| `src/output_manager.py` | 編集 | `OutputFiles`/`OutputConfig` 拡張、保存分岐追加 |
| `src/processor/processor.py` | 編集 | `_generate_outputs()` で `.md`/`.mmd` パスを収集 |
| `src/web/app.py` | 編集 | ダウンロード API と `save_mermaid_and_rebuild()` を拡張 |
| `config/config.py` | 編集 | 編集可能出力フラグ追加 |
| `tests/test_diagram_generator.py` | 編集 | `.md`/`.mmd` 保存テスト追加 |
| `tests/test_web_api.py` | 編集 | ダウンロード API テスト追加 |
| `README.md` | 編集 | 新規出力形式の説明追加 |

---

## ロールバック計画

各ステップは独立しており、問題発生時は該当ファイルを git  revert することでロールバック可能。

