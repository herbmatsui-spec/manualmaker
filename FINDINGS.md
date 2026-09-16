# 調査結果と修正手順

## 調査のまとめ
DEPLOYMENT_GUIDE.md に従ってデプロイを試みたが、以下の理由で失敗した。

1. ガイドは JavaScript の Pages Functions を前提としているが、本プロジェクトの API は Python で実装されている。
2. ガイドの wrangler.toml 設定が不適切で、`pages_build_output_dir` が欠如している。
3. 本プロジェクトは Workers デプロイメントに最適化されており、既存の wrangler.toml （manual_processor/wrangler.toml）は Workers 用に設定されている。
4. Wrangler のバージョン互換性や設定の詳細により、`wrangler pages dev` が functions ディレクトリを正しく認識しない。

## 正しいデプロイメント手順（Workers デプロイメント）
本プロジェクトは Cloudflare Workers としてデプロイすることを推奨する。以下の手順でローカルテストとデプロイを行う。

### 前提条件
- Wrangler がインストール済み（`npm install -g wrangler`）
- Cloudflare アカウントがあり、API トークンを取得済み
- .env.local ファイルに API キーを設定済み（以前の手順参照）

### 手順
1. プロジェクトのルート（manual_processor ディレクトリ）に移動：
   ```bash
   cd /workspaces/manualmaker/manual_processor
   ```

2. 環境変数を設定（既に .env.local が存在する場合はこのステップをスキップ）：
   ```bash
   echo "GOOGLE_API_KEY=your_actual_google_api_key" >> .env.local
   echo "GEMINI_API_KEY=your_actual_gemini_api_key" >> .env.local
   echo "ENVIRONMENT=production" >> .env.local
   ```

3. シークレットを設定（必要な場合）：
   ```bash
   wrangler secret put GOOGLE_API_KEY
   wrangler secret put GEMINI_API_KEY
   ```

4. ローカルで Workers を起動してテスト：
   ```bash
   wrangler dev
   ```
   これにより、http://localhost:8788 で Workers が起動する。

5. ヘルスチェックをテスト：
   ```bash
   curl http://localhost:8788/api/health
   ```
   期待される応答: `{"status":"ok"}`

6. 他のエンドポイントをテスト（例）：
   ```bash
   curl http://localhost:8788/api/config
   ```

7. 本番環境にデプロイ：
   ```bash
   wrangler publish
   ```
   または、特定の環境にデプロイする場合：
   ```bash
   wrangler publish --env production
   ```

### 注意点
- 本番デプロイ前に、wrangler.toml の ID プレースホルダーを実際の Cloudflare リソース ID に置き換える必要がある。
- リソース ID は、以下のコマンドで取得できる（事前にリソースを作成している必要がある）：
  ```bash
  wrangler kv: namespace create "FILES"
  wrangler r2 bucket create "manual-processor-files"
  wrangler d1 create "manual-maker-db"
  wrangler queues create "manual-processor-queue"
  ```
  出力された ID を wrangler.toml に反映する。

## 結論
DEPLOYMENT_GUIDE.md は Pages Functions デプロイメントを前提としているが、本プロジェクトは Workers デプロイメントに最適化されている。したがって、ガイドの手順ではなく、上記の Workers デプロイメント手順を使用することを推奨する。