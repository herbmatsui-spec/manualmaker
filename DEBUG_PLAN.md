# デバッグ計画書: DEPLOYMENT_GUIDE.md に従ったデプロイメントエラー

## 目的
DEPLOYMENT_GUIDE.md の手順に従ってデプロイを実行した際に発生するエラーを特定し、修正する。

## 再現手順
1. DEPLOYMENT_GUIDE.md のステップ 1～6 を実行（リポジトリクローン、依存関係インストール、環境変数設定、ローカルテスト）。
2. ステップ 7～12 を実行（Cloudflare リソース作成）。
3. ステップ 13: ガイドに従って wrangler.toml をプロジェクト ルートに作成。
4. ステップ 14: `wrangler` コマンドでリソース ID を取得し、wrangler.toml に反映。
5. ステップ 15: シークレットを設定。
6. ステップ 16: `wrangler pages dev ./manual_processor/functions/api` を実行し、ローカルで Pages Functions をテスト。
7. ステップ 17: ヘルスチェックエンドポイントをテスト（ここでエラーが発生する可能性がある）。

## 仮説とテスト計画

### 仮説 1: wrangler.toml の設定が間違っている
- ガイドの wrangler.toml には、`pages_build_output_dir` が欠けている（Pages Functions に必須）。
- ガイドの wrangler.toml には `[pages]` セクションが欠けている。
- ガイドの wrangler.toml の `queues` 設定の形式が間違っている（配列ではなくオブジェクトが必要か？）。
- テスト: 正しい wrangler.toml を作成し、`wrangler pages dev` を実行してみる。
  - 正しい wrangler.toml の例:
    ```
    name = "manual-maker"
    compatibility_date = "2024-01-01"
    pages_build_output_dir = "./dist"  # 必要に応じて調整
    [[kv_namespaces]]
    binding = "FILES"
    id = "<PLACEHOLDER>"
    [[r2_buckets]]
    binding = "BUCKET"
    bucket_name = "manual-processor-files"
    [[d1_databases]]
    binding = "DB"
    database_name = "manual-maker-db"
    database_id = "<PLACEHOLDER>"
    ```
  - 注: `pages_build_output_dir` は必須だが、実際にビルド出力がない場合はダミーのディレクトリを指定できる。

### 仮説 2: 言語のミスマッチ（JavaScript vs Python）
- ガイドは JavaScript の Pages Functions を前提としているが、プロジェクトは Python で実装されている。
- Python の Pages Functions は、`functions` ディレクトリ内の `.py` ファイルで `on_request` 関数を定義する。
- テスト: `functions` ディレクトリに簡単な Python ファイル（例: `test.py`）を作成し、`wrangler pages dev ./functions` を実行して `/test` エンドポイントが動作するか確認する。

### 仮説 3: 関数ディレクトリのパスが間違っている
- ガイドのステップ 16 では `wrangler pages dev ./manual_processor/functions/api` と指定しているが、これは `api` サブディレクトリを指している。
- しかし、プロジェクトの `functions/__init__.py` がカスタムルーターを提供しているため、正しくは `functions` ディレクトリ全体を指すべきである。
- テスト: `wrangler pages dev ./manual_processor/functions` を実行し、ヘルスチェックエンドポイント（`/api/health`）が動作するか確認する。

### 仮説 4: カスタムルーター（functions/__init__.py）が Wrangler と互換性がない
- Wrangler のデフォルトの Python Functions サポートは、ファイルベースのルーティングを期待している（`hello.py` → `/hello` ルート）。
- プロジェクトの `__init__.py` は独自のルーティングロジックを実装しているため、Wrangler がこれを正しく認識しない可能性がある。
- テスト: `__init__.py` を一時的にリネームまたは削除し、`functions` ディレクトリに簡単な Python ファイルを置いて、Wrangler がルートを認識するか確認する。

### 仮説 5: 互換性日付が設定されていない
- 最近の Wrangler バージョンでは `compatibility_date` が必須になっている。
- テスト: `wrangler toml` に `compatibility_date = "2024-01-01"` を追加し、再度試す.

## 期待される結果
- 正しい wrangler.toml と正しいコマンドを使用すれば、`wrangler pages dev` が正常に起動し、`/api/health` エンドポイントが `{"status":"ok"}` を返す。

## 修正計画
1. wrangler.toml をプロジェクト ルートに作成し、必要なフィールドを追加する。
2. `wrangler pages dev` のコマンドを修正し、正しい関数ディレクトリを指すようにする。
3. 必要に応じて、プロジェクトの関数構造を標準的な Pages Functions の conventions に合わせる（またはカスタムルーターを維持しつつ Wrangler と互換性があるように調整する）。
4. 互換性日付を設定する.

## 次のステップ
この計画に基づいて、まず wrangler.toml を修正し、次にコマンドを修正し、最後にヘルスチェックが通ることを確認する。
その後、ガイドの後のステップ（ファイルアップロードなど）もテストする.