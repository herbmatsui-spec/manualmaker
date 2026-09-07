# セキュリティポリシー

**対象バージョン**: Manual Processor v2.1.0以降
**最終更新**: 2026-09-07

## 1. 概要

Manual Processorは、手書きマニュアルPDFファイルを処理する際に、以下の種類の機密情報を取り扱う可能性があります：

- 個人情報 (PII)
- API キー (Google Gemini, Google Cloud Vision)
- アップロードされたファイル内容

本ポリシーは、これらの情報を保護するための要件と運用方針を定めるものです。

## 2. サポート対象PIIパターン

以下のパターンに対する自動検出・マスキングを提供します：

| パターン | 説明 | 例 |
|---------|------|-----|
| EMAIL | メールアドレス | `user@example.com` |
| PHONE_JP | 日本の電話番号 | `03-1234-5678` |
| MY_NUMBER | マイナンバー | `1234-5678-9012` |
| PASSPORT | パスポート番号 | `TR1234567` |
| POSTAL_JP | 郵便番号 | `123-4567` |
| CREDIT_CARD | クレジットカード番号 | `4111-1111-1111-1111` |
| IP_ADDRESS | IPアドレス | `192.168.1.1` |
| BANK_ACCOUNT | 銀行口座番号 | (要設定) |

## 3. API キー管理方針

### 3.1 推奨管理方法（優先度順）

1. **OSキーチェーン** (`keyring` ライブラリ)
   - macOS: Keychain Access
   - Windows: Credential Manager
   - Linux: Secret Service (GNOME Keyring, KWallet)

2. **環境変数** (本番環境)
   - `GEMINI_API_KEY`
   - `GOOGLE_API_KEY`
   - 実行環境ごとに分離すること

3. **設定ファイル** (非推奨)
   - 開発用途のみ
   - リポジトリにコミットしないこと

### 3.2 禁止事項

- API キーをソースコードにハードコードしない
- API キーをログに出力しない
- API キーを平文でGitリポジトリにコミットしない
- API キーをWeb UI経由で公開しない

## 4. 監査ログ保持期間

| ログ種別 | 保持期間 | 保存形式 |
|---------|---------|---------|
| セキュリティイベント | 90日 | JSON Lines (`.log`) |
| PII マスキングイベント | 30日 | JSON Lines |
| API 呼び出し履歴 | 7日 | JSON Lines |
| エラーログ | 30日 | テキスト |

### 4.1 ログローテーション

- 日次ローテーションを推奨
- 古いログは自動アーカイブまたは削除

## 5. 入力検証ルール

### 5.1 ファイルアップロード

| 項目 | 制約 |
|------|------|
| ファイル形式 | PDF のみ (`.pdf` 拡張子) |
| マジックバイト | `%PDF-` で始まること |
| 最大サイズ | デフォルト 100MB (設定可能) |
| Content-Type | `application/pdf` |

### 5.2 API リクエスト

| 項目 | 制約 |
|------|------|
| レート制限 | 60リクエスト/分/IP (デフォルト) |
| リクエストサイズ | 10MB 以下 (JSON body) |
| 認証 | (将来実装) |

### 5.3 入力サニタイゼーション

- ファイル名は英数字・ハイフン・アンダースコア・ドットのみ許可
- パストラバーサル対策 (`..`, `/`, `\` を含むパスを拒否)
- SQLインジェクション対策 (ORM/パラメータ化クエリ使用)

## 6. 通信セキュリティ

### 6.1 本番環境

- HTTPS 必須 (TLS 1.2 以上)
- HSTS ヘッダー設定
- 証明書の自動更新

### 6.2 開発環境

- HTTP 可 (localhost のみ)
- 本番同様の CORS 設定を推奨

## 7. 依存関係管理

### 7.1 脆弱性スキャン

- CI にて `pip-audit` を実行
- 週次の脆弱性情報確認
- 重大脆弱性は24時間以内に対応

### 7.2 アップデート方針

| 種別 | 対応期限 |
|------|---------|
| セキュリティパッチ | 7日以内 |
| バグフィックス | 30日以内 |
| メジャーアップデート | 90日以内 |

## 8. インシデント対応

### 8.1 検出

- 監査ログの定期監視
- 異常パターンのアラート設定

### 8.2 初動対応

1. 影響範囲の特定
2. 該当 API キーの無効化
3. ログの保全
4. 関係者への通知

### 8.3 報告先

- セキュリティ担当: (要設定)
- 問い合わせ先: (要設定)

## 9. ベストプラクティス

### 9.1 開発者向け

- API キーは環境変数経由で読み込む
- 新規PII パターンを追加したらテストも追加
- ログには機密情報を含めない
- コードレビュー時にセキュリティ観点を含める

### 9.2 運用者向け

- API キーのローテーション (90日ごと推奨)
- アクセスログの定期監査
- バックアップの暗号化

## 10. 変更履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2026-09-07 | 1.0.0 | 初版作成 |
| 2026-09-07 | 1.1.0 | セキュリティ強化実装 (ステップ1-12完了) |

## 11. 実装詳細 (2026-09-07 追記)

### 11.1 入力バリデーション

- **ファイル**: `src/utils/validators.py`
- **機能**: ファイルサイズ、PDF形式、UUID、言語コード、ファイル名の検証
- **検証**: 15ユニットテスト (tests/test_security.py)

### 11.2 APIキー暗号化ストレージ

- **ファイル**: `src/security/keyring_store.py`
- **機能**: OSキーチェーン経由の安全なAPIキー保存
- **フォールバック**: 環境変数 (MANUAL_PROCESSOR_*)

### 11.3 PIIパターン外部化

- **ファイル**: `config/pii_patterns.yaml`
- **機能**: 9種類のPIIパターンをYAMLで管理
- **動的読み込み**: `SecurityManager._load_pii_patterns()`

### 11.4 構造化監査ログ

- **ファイル**: `src/security/audit_logger.py`
- **形式**: JSON Lines (.jsonl)
- **機能**: ローテーション、イベント種別、統計情報

### 11.5 CORS設定厳格化

- **デフォルト**: `["http://localhost:3000", "http://localhost:8000"]`
- **環境変数**: `WEB_CORS_ORIGINS` (カンマ区切り)
- **設定**: `config/config.py` の `from_env()` メソッド

### 11.6 ファイルアップロード検証

- **検証項目**:
  - 拡張子チェック (.pdf のみ)
  - Content-Type チェック (application/pdf)
  - マジックバイトチェック (%PDF-)
  - サイズ制限 (config.web_upload_max_mb)

### 11.7 レート制限ミドルウェア

- **ファイル**: `src/web/middleware/rate_limit.py`
- **機能**: スライディングウィンドウ方式のレート制限
- **デフォルト**: 60リクエスト/分/IP
- **ヘッダー**: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset

### 11.8 セキュリティヘッダー

- **ファイル**: `src/web/middleware/security_headers.py`
- **ヘッダー**:
  - X-Content-Type-Options: nosniff
  - X-Frame-Options: DENY
  - Strict-Transport-Security (HTTPSのみ)
  - Content-Security-Policy
  - X-XSS-Protection: 1; mode=block

### 11.9 センシティブログマスキング

- **ファイル**: `src/utils/log_filter.py`
- **機能**: ログ出力時に機密情報を自動マスク
- **対象**: APIキー、Bearerトークン、メール、クレジットカード、電話番号

### 11.10 テストカバレッジ

- **ファイル**: `tests/test_security.py`
- **テスト数**: 31テスト
- **カテゴリ**:
  - TestValidators (15テスト)
  - TestPIIMasking (7テスト)
  - TestAuditLogger (3テスト)
  - TestLogFilter (5テスト)

### 11.11 検証結果

```
=== Verification 1 (ステップ1-3) ===
✓ Validators: OK
✓ Env storage: OK
✓ PII masking: OK
✓ Audit logger: OK
✓ SECURITY.md: OK

=== Verification 2 (ステップ4-6) ===
✓ CORS: OK
✓ PII patterns: OK
✓ PII masking: OK
✓ Audit logger: OK
✓ Validators: OK
✓ Keyring fallback: OK

=== Verification 3 (ステップ7-9) ===
✓ File upload validation: OK
✓ Rate limiting: OK
✓ Security headers: OK
```

## 12. 参考リンク

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE (Common Weakness Enumeration)](https://cwe.mitre.org/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Python keyring](https://pypi.org/project/keyring/)
