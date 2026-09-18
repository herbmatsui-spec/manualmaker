# Phase 3: プラットフォーム統合 - 実装計画書

## 概要
Phase 1-2で構築した強固な基盤の上で、プラットフォームの統合と標準化を進める。PythonとCloudflare Workersの二重維持ではなく、いずれか一方に統合し、API仕様の明確化とデプロイ自動化を実現する。

**目標期間**: 2週間  
**前提**: Phase 1-2 完了済み

---

## Step 1: プラットフォーム選定と移行戦略の決定

### 目的
Python Web API と Cloudflare Workers のどちらか一方に統合する方針を決定する

### 作業内容
1. `docs/PLATFORM_DECISION.md` 新規作成
2. 比較表作成：
   - **Python (FastAPI + Celery + Redis)**:
     - ✅ 重い処理（OCR、PDF生成）に適す
     - ✅ フル機能ライブラリ利用可能
     - ✅ 複雑なワークフロー制御可能
     - ❌ サーバー管理必要
     - ❌ コールドスタート遅延なしだがスケールに時間
   - **Cloudflare Workers**:
     - ✅ エッジデプロイ、低レイテンシ
     - ✅ 自動スケール、サーバーレス
     - ✅ 無料枠あり
     - ❌ CPU時間制限 (50ms標準、30秒上限)
     - ❌ 大きなライブラリ制限 (PyTorch等不可)
     - ❌ 状態管理にKV/R2依存（遅延・コスト）
3. 推奨: **ハイブリッドアプローチ**
   - 軽量エンドポイント (認証、設定、進捗取得): Workers
   - 重い処理 (OCR、PDF生成、AI処理): Python バックエンド
   - Workers → Python への内部API呼び出しで連携
4. 方針決定後、チーム全員に共有

### 確認方法
- 決定文書完了
- 全員が方針を理解していること

---

## Step 2: Workers専用軽量APIレイヤーの設計

### 目的
Workers側で扱うべき機能を特定し、最小限のAPIに絞る

### 作業内容
1. `manual-maker-workers/src/routes/` を整理
2. Workers側に残すエンドポイント：
   - `/api/health` (ヘルスチェック)
   - `/api/config` (公開設定)
   - `/api/i18n/*` (国際化)
   - `/api/security/status` (セキュリティ状態)
   - `/api/security/patterns` (PIIパターン)
   - `/api/auth/*` (認証関連)
   - `/api/upload` (アップロード開始 - メタデータのみ)
   - `/api/process/{fileId}` (処理開始指示)
   - `/api/process/{fileId}/progress` (進捗取得)
   - `/api/results/{fileId}` (結果メタデータ取得)
   - `/api/download/*` (ダウンロード - R2経由)
3. 削除/移行するエンドポイント：
   - 全ての重い処理関連 (`/api/gemini/*`, `/api/vision/*`, `/api/mermaid/*` 等)
   - 複雑なビジネスロジックを含むもの
4. `docs/API_SPLIT.md` に取り決めを記録

### 確認方法
- Workers側コードが軽量化されていること
- 重い処理はPythonバックエンドに委譲されていること

---

## Step 3: 内部API仕様の定義 (Pythonバックエンド向け)

### 目的
WorkersからPythonバックエンドへの内部通信用APIをRESTまたはgRPCで定義する

### 作業内容
1. `docs/INTERNAL_API_SPECS.md` 新規作成
2. 内部APIエンドポイント定義：
   - `POST /internal/v1/ocr` : 画像OCR処理
     - Input: `{ image: base64, hints: ['ja','en'] }`
     - Output: `{ text: string, confidence: number }`
   - `POST /internal/v1/gemini/process` : ドキュメント処理
     - Input: `{ text: string, options: ProcessingOptions }`
     - Output: `{ summary: string, key_points: string[], sections: [...] }`
   - `POST /internal/v1/diagram/generate` : フローチャート生成
     - Input: `{ text: string, sections: [], key_points: [] }`
     - Output: `{ mermaid: string, png: base64? }`
   - `POST /internal/v1/pdf/generate` : PDF生成
     - Input: `{ content: string, title: string, options: dict }`
     - Output: `{ pdf: base64 }`
   - `POST /internal/v1/docx/generate` : Word文書生成
   - `POST /internal/v1/audio/generate` : 音声生成
   - `POST /internal/v1/security/mask` : PIIマスキング
3. 認証: 内部ネットワークのみまたは共有シークレット
4. バージョニング: `/internal/v1/*` 形式

### 確認方法
- 仕様書完了
- 両チームが理解していること

---

## Step 4: WorkersからPythonバックエンドへのHTTPクライアントラッパー

### 目的
Workers側からPythonバックエンドの内部APIを簡単に呼び出せるラッパーを作る

### 作業内容
1. `requirements.txt` (workers) に `node-fetch@^3.3.0` 相当（既に組み込みfetch使用）確認
2. `manual-maker-workers/src/lib/internal-api.ts` 新規作成
3. `InternalApiClient` クラス実装：
   - コンストラクタ: `baseUrl: string` (環境変数 `INTERNAL_API_URL` から)
   - メソッド群:
     - `async ocr(image: string, hints: string[]): Promise<OcrResult>`
     - `async processDocument(text: string, options: ProcessingOptions): Promise<ProcessResult>`
     - `async generateDiagram(text: string, sections: Section[], keyPoints: string[]): Promise<DiagramResult>`
     - `async generatePdf(content: string, title: string, options: PdfOptions): Promise<Blob>`
     - 同様に他のエンドポイント
   - 各メソッドで:
     - タイムアウト設定 (30秒)
     - エラーハンドリング (詳細ログ)
     - リトライロジック (指数バックオフ、最大3回)
4. エラーハンドリング統一:
   - `InternalApiError` クラス
   - エラーコード: `TIMEOUT`, `UNAVAILABLE`, `INTERNAL_ERROR`, `BAD_REQUEST`

### 確認方法
- モックサーバー起動 → クライアントで呼び出し → 正常応答
- エラーケース → 適切な例外スロー

---

## Step 5: Workers側エンドポイントの内部API委譲実装

### 目的
Workers側の重い処理エンドポイントを内部API呼び出しに置き換える

### 作業内容
1. `manual-maker-workers/src/routes/gemini.ts` を書き換え：
   - 全てのエンドポイントを `InternalApiClient.processDocument()` 呼び出しに置換
   - 例: `generateContent` → `/internal/v1/gemini/process`
   - 認証トークンは環境変数から取得してヘッダーに付与
2. `manual-maker-workers/src/routes/vision.ts` 同様に書き換え
3. `manual-maker-workers/src/routes/mermaid.ts` 書き換え：
   - `/api/mermaid/validate` → 簡易バリデーションは残す（軽量なので）
   - `/api/mermaid/render` → `/internal/v1/diagram/generate` 呼び出し
   - `/api/mermaid/regenerate` → `/internal/v1/gemini/process` 呼び出し（プロンプト工夫）
4. `manual-maker-workers/src/routes/upload.ts`：
   - アップロード完了後、`/internal/v1/process/start` 呼び出しでPythonバックエンドに処理依頼
5. `manual-maker-workers/src/routes/results.ts`、`/download.ts`：
   - 結果取得はPythonバックエンド経由か、直接R2/KVから（キャッシュ戦略検討）

### 確認方法
- Workers側エンドポイント呼び出し → Pythonバックエンドにリクエスト飛ぶこと
- レスポンスが正常に返ってくること
- エラー時は適切にハンドリングされること

---

## Step 6: 共有型定義の作成 (TypeScript → Python)

### 目的
Workers (TypeScript) と Python バックエンド間でデータ構造を共有し、不整合を防ぐ

### 作業内容
1. `shared/` ディレクトリをプロジェクトルートに作成
2. `shared/types.ts` 新規作成：
   - ProcessingOptions, ProcessingResult, GeminiResult 等のインターフェース定義
   - `export interface` 形式でエクスポート
3. `shared/schemas/` ディレクトリ作成
4. JSON Schema 形式でバリデーションルール定義：
   - `ocr-request.schema.json`
   - `process-request.schema.json`
   - 等
5. スクリプト `scripts/generate-pytypes.py` 作成：
   - JSON Schema から Python の `TypedClass` または `pydantic.BaseModel` 自動生成
   - `shared/schemas/*.json` → `manual_processor/src/shared/models.py`
6. 両サイドで同じ型定義を使用するようにコード修正

### 確認方法
- スキーマ変更時に両サイドの型が自動更新されること
- 不整合があるとビルド/テストでエラーになること

---

## Step 7: APIゲートウェイパターンの実装 (オプション)

### 目的
外部からのリクエストを適切なバックエンドにルーティングするゲートウェイを実装

### 作業内容
1. `manual-processor/src/gateway/` ディレクトリ新規作成
2. `main.py` または別のエントリーポイントで `GatewayApp` 作成：
   - ルーティングルール：
     - `/api/health`, `/api/config`, `/api/i18n/*` → Workersスタイルの軽量処理（直接処理）
     - `/api/auth/*` → Authサービス
     - `/api/upload*` → アップロード処理（メタデータ保存後バックエンドに委譲）
     - `/api/process/*` → 処理管理
     - `/api/internal/*` → 内部処理（Workerからの呼び出し専用）
     - その他 → 404
3. または、既存のFastAPIアプリにミドルウェア追加でパス別処理分岐
4. ドキュメント: `docs/GATEWAY_ROUTING.md`

### 確認方法
- 各パスで適切なハンドラーが呼ばれること
- 内部APIは外部から直接アクセス不可（ヘッダーまたはネットワーク制限）

---

## Step 8: Dockerイメージのマルチステージビルド最適化

### 目的
本番用Dockerイメージを小さく、セキュアに最適化する

### 作業内容
1. `Dockerfile` 新規作成（マルチステージ）：
   - Stage 1: ビルド環境
     - `FROM python:3.11-slim AS builder`
     - 依存関係インストール
     - ソースコードコピー
     - `pip install -r requirements-lock.txt --target /install`
   - Stage 2: ランタイム環境
     - `FROM python:3.11-slim`
     - システム依存関係のみインストール (`libglib2.0-0`, `smbclient` 等)
     - `/install` から必要なものだけコピー
     - 非 root ユーザーで実行
     - `EXPOSE 8000`
     - `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]`
2. `.dockerignore` 作成：
   - `__pycache__`, `*.pyc`, `tests/`, `docs/`, `.git/`, `bin/`, `obj/` 等を除外
3. `docker-compose.yml` 新規作成：
   - サービス: `api`, `redis`, `flower` (Celery監視)
   - ネットワーク設定
   - ボリュームマウント（開発時用）
4. `scripts/build-docker.sh` 作成：
   - ビルド、タグ付け、レジストリプッシュ
   - SBOM生成 (`syft` または `cosign`)

### 確認方法
- `docker build -t manualmaker:test .`
- `docker run -p 8000:8000 manualmaker:test` → アプリ起動
- イメージサイズ確認（目標: < 500MB）
- `docker scout` で脆弱性チェック

---

## Step 9: Kubernetesマニフェストの作成

### 目的
Kubernetes環境でのデプロイを自動化する

### 作業内容
1. `k8s/` ディレクトリ新規作成
2. `k8s/namespace.yaml`：`manual-maker` 名前空間
3. `k8s/configmap.yaml`：アプリケーション設定
4. `k8s/secret.yaml`：シークレット（外部からインジェクト推奨）
5. `k8s/deployment.yaml`：
   - レプリカ: 3 (最小)
   - リソース制限: `requests: memory="512Mi", cpu="250m"`, `limits: memory="1Gi", cpu="500m"`
   - ライブネス/ readiness プローブ: `/api/health`
   - ボリュームマウント: 一時ファイル用 `emptyDir`
6. `k8s/service.yaml`：ClusterIP サービス
7. `k8s/celery-worker-deployment.yaml`：Celeryワーカー用
8. `k8s/redis-deployment.yaml`：Redis（または外部マネージドサービス参照）
9. `k8s/hpa.yaml`：HorizontalPodAutoscaler（CPUまたはカスタムメトリクスベース）
10. `k8s/ingress.yaml`：Ingressコントローラー用（TLS終端）

### 確認方法
- `kubectl apply -f k8s/` でデプロイ可能
- Podが起動し、サービスが正常に動作すること
- HPAが負荷に応じてスケールすること

---

## Step 10: CI/CDパイプラインの強化

### 目的
コード変更から本番デプロイまでを自動化し、品質ゲートを設ける

### 作業内容
1. `.github/workflows/ci.yml` 強化：
   - フェーズ: lint → test (unit/integration) → build → security-scan → deploy-staging
   - `actions/setup-python` でキャッシュ
   - `pip-audit`, `bandit`, `safety` 実行
   - Dockerビルドとレジストリプッシュ
   - Staging環境へのデプロイとスモークテスト
2. `.github/workflows/cd.yml` 新規作成：
   - mainブランチへのマージでトリガー
   - 本番環境へのデプロイ (Argo CD または手動承認)
   - ブルーグリーンデプロイまたはカナリアリリース
   - デプロイ後モニタリングとロールバックトリガー
3. 環境別設定:
   - `.env.staging.example`, `.env.production.example`
   - `k8s/overlays/staging/` と `k8s/overlays/production/`
4. ロールバック手順ドキュメント: `docs/ROLLBACK_PROCEDURES.md`

### 確認方法
- プルリクエスト → CIが全パス → マージ → CDが本番デプロイ
- 障害発生時 → 自動ロールバックまたはワンクリックロールバック

---

## Step 11: APIドキュメントの自動生成と公開

### 目的
内部・外部APIのドキュメントを常に最新に保ち、開発者ポータルを提供する

### 作業内容
1. `manual-processor/src/web/app.py` に以下追加：
   - `from fastapi.openapi.utils import get_openapi`
   - カスタムOpenAPIスキーマ生成関数
   - `/docs` エンドポイント (Swagger UI)
   - `/redoc` エンドポイント (ReDoc)
   - `/openapi.json` エンドポイント (JSON形式)
2. スキーマに詳細な説明、例、レスポンスコード追加
3. `scripts/generate-api-docs.sh` 作成：
   - static HTML生成 (`mkdocs` または `redoc-cli`)
   - GitHub Pages に公開
4. `docs/API_USAGE_GUIDE.md` 作成：
   - 認証方法
   - エラーコード一覧
   - レート制限詳細
   - WebSocket使用方法
   - サンプルコード (curl, Python, JavaScript)

### 確認方法
- `/docs` で美しいSwagger UIが表示される
- `/openapi.json` が有効なJSON Schema
- 実際に試して動作する例が掲載されていること

---

## Step 12: 運用ツールとトラブルシューティングガイドの作成

### 目的
本番環境での運用を円滑にし、障害時に素早く対応できるようにする

### 作業内容
1. `docs/OPERATIONS_RUNBOOK.md` 作成：
   - 起動手順
   - 停止手順
   - バックアップ/リストア手順
   - データ移行手順
2. `docs/TROUBLESHOOTING.md` 作成：
   - よくあるエラーと対処法
   - パフォーマンスボトルネック特定方法
   - ログの見方
   - メトリクスの見方
3. 診断スクリプト作成：
   - `scripts/diagnose.sh`：システム状態チェック
   - `scripts/backup.sh`：バックアップ作成
   - `scripts/restore.sh`：バックアップリストア
   - `scripts/log-collector.sh`：ログ収集と解析
4. `scripts/health-check-full.sh` 作成：
   - コンポーネント間連携チェック
   - エンドツーエンドテスト実行
   - 結果をレポート出力

### 確認方法
- 運用マニュアル通りに作業できること
- 障害シミュレーションで迅速に対応できること
- バックアップから復旧可能であること

---

## 依存関係マッピング

```
Step 1 (プラットフォーム選定) → Step 2-12 全て
Step 2 (Workers軽量API)       → Step 3-5
Step 3 (内部API仕様)          → Step 4-6
Step 4 (内部APIクライアント)   → Step 5-6
Step 5 (Workers委譲実装)       → Step 4, 6
Step 6 (共有型定義)            → Step 4, 5
Step 7 (APIゲートウェイ)       → オプション、Step 2-6に影響
Step 8 (Docker最適化)          → 独立
Step 9 (K8sマニフェスト)       → Step 8に依存
Step 10 (CI/CD強化)            → Step 8, 9に依存
Step 11 (APIドキュメント)      → Step 2-6に依存
Step 12 (運用ツール)           → 全Stepに依存
```

## 推奨実施順序

| 週 | Steps | 備考 |
|----|-------|------|
| 1前半 | 1, 2, 3 | プラットフォーム決定→Workers軽量化→内部API仕様 |
| 1後半 | 4, 5, 6 | 内部APIクライアント→Workers実装→共有型定義 |
| 2前半 | 7, 8, 9 | ゲートウェイ(任意)→Docker最適化→K8sマニフェスト |
| 2後半 | 10, 11, 12 | CI/CD強化→APIドキュメント→運用ツール |

---

*Phase 1-2が完了していることを前提とする。Step 7のAPIゲートウェイはオプション。*