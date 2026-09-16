# Cloudflare 無料デプロイメント ガイド

このガイドでは、Manual Maker プロジェクトを Cloudflare の無料サービスのみを使用してデプロイする手順を 1～24 の小さなステップに分けて説明します。

## 前提条件
- Cloudflare アカウント（無料）
- Google AI Studio で Gemini API キー取得（無料枠利用可能）
- ローカル環境に Node.js と npm がインストール済み
- Wrangler CLI がインストール済み (`npm install -g wrangler`)

---

## ステップ 1～6: プロジェクト準備とローカル設定

**ステップ 1: リポジトリをクローン**
```bash
git clone <repository-url>
cd manualmaker
```

**ステップ 2: 必要な依存関係をインストール**
```bash
cd manual_processor
pip install -r requirements.txt
```

**ステップ 3: 環境変数テンプレートを作成**
```bash
cp .env.example .env.local
```

**ステップ 4: ローカル環境変数を設定**
`.env.local` ファイルを編集し、以下の値を設定:
```
ENVIRONMENT=development
GOOGLE_API_KEY=your-gemini-api-key-here
GEMINI_API_KEY=your-gemini-api-key-here
```

**ステップ 5: ローカルでテスト実行**
```bash
python -m pytest manual_processor/tests/integration/test_file_upload_download.py -v
```

**ステップ 6: すべての統合テストがパスすることを確認**
```bash
python manual_processor/tests/integration/run_verification.py
```
→ 「🎉 All infrastructure verification tests passed!」と表示されることを確認

---

## ステップ 7～12: Cloudflare リソースの作成

**ステップ 7: Cloudflare ダッシュボードにログイン**
https://dash.cloudflare.com

**ステップ 8: Workers & Pages を選択し、「Create Application」→「Pages」をクリック**

**ステップ 9: 「Connect to Git」を選択し、このリポジトリを連携**
- リポジトリ: manualmaker
- ビルドコマンド: `npm run build` (必要に応じて調整)
- ビルド出力ディレクトリ: `dist` または `public`

**ステップ 10: R2 バケットを作成**
- ダッシュボード → R2 → 「Create bucket」
- バケット名: `manual-processor-files` (または任意の名前)
- リージョン: 自動選択か希望のリージョン

**ステップ 11: D1 データベースを作成**
- ダッシュボード → Workers & Pages → D1 → 「Create」
- データベース名: `manual-maker-db`
- スキーマは後でマイグレーションスクリプトで作成

**ステップ 12: キューを作成**
- ダッシュボード → Workers & Pages → Queues → 「Create Queue」
- キュー名: `manual-processor-queue`

---

## ステップ 13～18: Wrangler 設定とシークレット

**ステップ 13: wrangler.toml を作成/編集**
プロジェクトのルートに wrangler.toml ファイルを作成:
```toml
name = "manual-maker"
main = "./manual_processor/functions/api/index.js"
compatibility_date = "2024-01-01"

[[kv_namespaces]]
binding = "FILES"
id = "<your-kv-namespace-id>" # 後で自動生成

[[r2_buckets]]
binding = "BUCKET"
bucket_name = "manual-processor-files"

[[d1_databases]]
binding = "DB"
database_name = "manual-maker-db"
database_id = "<your-d1-database-id>" # 後で自動生成

[[queues]]
binding = "QUEUE"
queue_name = "manual-processor-queue"
```

**ステップ 14: Wrangler でリソースIDを自動取得**
```bash
wrangler kv: namespace create "FILES"
wrangler r2 bucket create "manual-processor-files"
wrangler d1 create "manual-maker-db"
wrangler queues create "manual-processor-queue"
```
→ 出力された ID を wrangler.toml に反映

**ステップ 15: シークレットを設定 (Gemini API キー)**
```bash
wrangler secret put GOOGLE_API_KEY
wrangler secret put GEMINI_API_KEY
```
→ プロンプトにしたがって API キーを入力

**ステップ 16: ローカルで Pages Functions をテスト**
```bash
wrangler pages dev ./manual_processor/functions/api
```
→ http://localhost:8788 で API が利用可能になることを確認

**ステップ 17: ヘルスチェックエンドポイントをテスト**
```bash
curl http://localhost:8788/api/health
```
→ `{"status":"ok"}` が返されることを確認

**ステップ 18: その他のエンドポイントを簡易テスト**
- `/api/config`
- `/api/upload` (モックファイルで)
- `/api/process` (モックファイルIDで)

---

## ステップ 19～24: デプロイと検証

**ステップ 19: プロジェクトをビルド (必要な場合)**
```bash
# フロントエンドがある場合
npm run build
# バックエンドのみの場合は不要
```

**ステップ 20: Cloudflare Pages にデプロイ**
```bash
wrangler pages deploy ./manual_processor/functions/api --project-name manual-maker
```
→ デプロイURLが表示される (例: https://manual-maker.pages.dev)

**ステップ 21: デプロイ後のヘルスチェック**
```bash
curl https://manual-maker.pages.dev/api/health
```
→ `{"status":"ok"}` が返されることを確認

**ステップ 22: ファイルアップロードエンドポイントをテスト**
```bash
curl -X POST "https://manual-maker.pages.dev/api/upload" \
  -F "file=@/path/to/test.pdf"
```
→ アップロード成功レスポンスが返されることを確認

**ステップ 23: WebSocket 接続をテスト**
```bash
wscat -c "wss://manual-maker.pages.dev/api/ws/progress?file_id=test123"
```
→ 接続が確立され、ピング/ポングがやり取りできることを確認

**ステップ 24: モニタリングとメンテナンスの設定**
- Cloudflare ダッシュボードで「Analytics」→「Workers & Pages」を確認
- エラーレートとリクエスト数を監視
- 必要に応じてワーカーのログを確認: `wrangler pages dev --log-level debug`
- 定期的に未使用ファイルをクリアするスクリプトを設定（オプション）

---

## トラブルシューティング

### よくある問題と解決策
1. **「Module not found」エラー**
   - ローカルで `pip install -r requirements.txt` を実行済みか確認
   - Cloudflare Pages Functions では純粋な Python ライブラリのみサポート

2. **認証エラー (401/403)**
   - Wrangler シークレットが正しく設定されているか: `wrangler secret list`
   - 環境変数名がコードと一致しているか (`GOOGLE_API_KEY` vs `GEMINI_API_KEY`)

3. **R2 へのアクセスエラー**
   - バケット名が wrangler.toml と実際のバケット名が一致しているか
   - ロールバインディングが正しく設定されているか（デフォルトで OK）

4. **キューが処理されない**
   - ワーカーから `QUEUE.send()` が正しく呼び出されているか
   - コンシューマーワーカー（別途設定が必要）がデプロイされているか

### 次のステップ
- カスタムドメインを設定 (Pages Settings → Custom domains)
- アクセス制御を追加 (Cloudflare Access)
- 使用量アラートを設定 (Notifications → Alert Rules)
- 自動スケーリングの設定 (ほとんど自動だが、ワーカーのインスタンス数を監視)

---
*このガイドは 2026 年 9 月時点の情報に基づいています。Cloudflare のサービス仕様や無料枠は変更される可能性がありますので、最新情報は公式ドキュメントをご確認ください。*