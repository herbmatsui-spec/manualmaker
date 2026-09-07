# Contributing

## 開発セットアップ

```bash
git clone <repo>
cd manualmaker/manual_processor
pip install -e .[dev]
pre-commit install    # 任意
```

## テスト

```bash
# ユニットテスト
python -m pytest tests/ -v

# カバレッジ付き
python -m pytest tests/ --cov=src --cov=config --cov-fail-under=65

# クリーンアップ
python scripts/clean_repo.py
```

## コーディング規約

- Type hints を使う
- docstring は Google 形式
- 1 ファイル 1 責務を心がける
- 副作用は orchestrator に集約する

## プルリクエスト

1. `feature/<name>` ブランチを切る
2. テストを追加
3. `python -m pytest tests/ -q` が全件 pass することを確認
4. PR を作成し、CI が green になることを確認

## リリース手順

```bash
./scripts/release.sh 2.2.0
```