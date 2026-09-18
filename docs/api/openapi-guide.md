# Workers OpenAPI利用ガイド

## 対象・閲覧

対象は[Workersアプリ](../../manual-maker-workers/src/app.ts)。旧Python APIや別Worker構成とは区別する。

リポジトリルートで開発サーバーを起動し、動的なOpenAPI 3.1仕様を取得する。

```sh
npm --prefix manual-maker-workers run dev
# 別ターミナルで実行
curl --fail http://localhost:8787/api/doc -o /tmp/manualmaker-openapi.json
```

本番では承認済みWorkerホストの同じパスを使う。この動的仕様が現行Workersの正であり、[静的仕様](openapi.yaml)との自動同期は実装していない。Swagger UIの組み込みは任意項目として未実装。取得したJSONはローカルのSwagger Editor等で閲覧できる。非公開仕様や社内URLを外部サービスに送信しないこと。

## SDK生成例

OpenAPI 3.1対応のOpenAPI Generatorを用意し、チームでバージョンを固定する。以下はCLI導入済みの場合の例。生成先はアプリ本体と分離する。

```sh
openapi-generator-cli validate -i /tmp/manualmaker-openapi.json
openapi-generator-cli generate \
  -i /tmp/manualmaker-openapi.json \
  -g typescript-fetch \
  -o /tmp/manualmaker-client
```

入力仕様、Generatorバージョン、生成オプションをリリースごとに記録し、生成SDKの型チェックとテスト環境での結合試験を行う。SDK生成コマンド自体は今回未実行。上流APIの任意JSON、Range、WebSocketには個別のクライアント処理が必要であり、生成だけで動作保証とはならない。

## 契約の保守と検証

[ルート登録](../../manual-maker-workers/src/routes/index.ts)と[契約定義](../../manual-maker-workers/src/routes/openapi.ts)を同時に更新する。[入力スキーマ](../../manual-maker-workers/src/lib/schemas.ts)を実行時検証と共用し、仕様追加のためにハンドラーを重複登録しない。

```sh
npm --prefix manual-maker-workers run typecheck
npm --prefix manual-maker-workers test
```

[網羅性テスト](../../manual-maker-workers/src/routes/__tests__/openapi-inventory-contract.test.ts)は、本番アプリの業務操作と公開仕様の一致、パスパラメーター、操作IDの重複を確認する。仕様取得自身のルートと共通ミドルウェアは業務操作から除外する。

網羅性は全レスポンスのJSON Schema適合を証明するものではない。個別契約テストで成功・入力エラー・欠損・依存障害を検証する。透過プロキシでは上流JSONを過度に制限せず、転送内容とアプリが変換するエラーを検証する。完全なOpenAPIメタスキーマ検証は今回のテストに含まれない。

## CI

[Workers専用CI](../../.github/workflows/workers-contracts.yml)でロックファイルによる依存導入、型チェック、契約を含む全テスト、ドライランビルドを順に実行する。失敗を無視しない。秘密情報やデプロイ権限は使わず、既存の別Worker/Python向けCIは変更しない。

ワークフローの構文・対象・権限とローカルテスト・ビルドは検証済み。GitHub上の初回実行とブランチ保護の必須チェック設定は未検証。ドライランはリソース作成、権限確認、Cron発火を保証せず、配置設定のKV識別子も仮値のままである。

## バージョニング・非互換変更

- API情報のバージョン、変更履歴、SDKのリリースを同期する。
- 任意項目追加でも、未知項目を拒否するクライアントとの互換性は確認する。
- 必須項目追加、型変更、削除、ステータス変更は非互換変更として扱う。必要なら新APIバージョンを併設し、移行手順・旧仕様の終了日を告知する。
- 今回の[進捗HTTP取得](../../manual-maker-workers/src/routes/progress.ts:21)は欠損応答を500から404へ変更。不正識別子は400、エラー本文は共通の構造化形式になった。クライアントの再試行・エラー表示を調整する。

## 現在の制約

- Geminiのストリーム生成もJSON全体をバッファーして返す。SSE中継ではない。
- 外部APIの再試行超過は500。非再試行対象の上流拒否とAPIキー未設定は502。
- Visionは200本文内に画像単位のエラーを含むことがある。
- WebSocketの契約は101・426・500のハンドシェイクのみ。フレームや実101接続は未検証。同期セットアップ失敗と非同期転送失敗で500本文の形が異なる。
- 詳細ヘルスは200/503、切替状況は状態にかかわらず200。可用性検査は副データの整合性を保証しない。
- アップロード削除は副R2へ複製しない。処理一覧はKVフォールバック記録のみ。
- 共通ミドルウェアのエラー本文は個別業務エラーと形が異なることがある。全エラーを単一形式と仮定しない。
- 実Cloudflare、ブラウザー、外部APIでの検証は別途必要。

履歴は[段階検証記録](../improvement-plans/C7-validation-log.md)を参照。
