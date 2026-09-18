# P7: マルチリージョン R2 & KV フェイルオーバー

## 概要
R2バケットとKVネームスペースの地理的冗長化とフェイルオーバーメカニズムにより、システムの可用性と災害復旧能力を向上させる。マルチリージョン設定とバックアップ戦略を実装する。

---

## ステップ1: R2マルチリージョン設定確認・最適化
**ファイル**: `wrangler.toml`
- 現在の設定を確認し、マルチリージョンまたは自動ロケーションに変更
- 単一リージョンからマルチジュリスディクションへの移行ガイド

```toml
# 現在（単一リージョン推定）
[[r2_buckets]]
binding = "BUCKET"
bucket_name = "manual-processor-files"

# 推奨変更（マルチジュリスディクション）
[[r2_buckets]]
binding = "BUCKET"
bucket_name = "manual-processor-files"
# location_type = "auto"  # 自動選択（利用可能な場合）
# または明示的にマルチリージョンを指定
# 例: location = "WEUR"  # 西ヨーロッパ（実際のリージョンコードはドキュメント参照）

# 代替案: 複数バケットを用意してアプリケーションレベルでレプリケーション
# ただし、これは複雑になるため、まずはR2ネイティブのマルチリージョン機能を利用
```

**注意**: 
- R2のマルチジュリスディクション機能はエンタープライズプラン向けの場合がある
- フリーティアでは単一リージョンしか利用できない可能性あり
- その場合は、アプリケーションレベルでのレプリケーション戦略を検討

**確認方法**: 
- `wrangler bucket info manual-processor-files` で場所情報確認
- ダッシュボードでの場所設定確認

---

## ステップ2: R2レプリケーション戦略実装（アプリケーションレベル）
**ファイル**: `src/lib/r2-replication.ts` (新規)
- フリーティア制約があるため、アプリケーションレベルでのレプリケーションを実装
- セカンダリバケットへの非同期コピー

```typescript
import type { Env } from '../lib/types';

export class R2Replication {
  constructor(
    private readonly primary: R2Bucket,
    private readonly secondary: R2Bucket, // 別のバケット名で設定必要
    private readonly enabled: boolean = true
  ) {}

  /**
   * オブジェクトをセカンダリバケットに非同期コピー
   * ファイアアンドフォーゲット方式（エラーはログのみ）
   */
  async replicateObject(key: string): Promise<void> {
    if (!this.enabled) return;

    try {
      // プライマリからオブジェクト取得
      const obj = await this.primary.get(key);
      if (!obj) {
        console.warn(`Object not found for replication: ${key}`);
        return;
      }

      // メタデータ取得
      const { httpEtag, httpMetadata } = obj;
      const body = obj.body; // ReadableStream

      // セカンダリに書き込み
      await this.secondary.put(key, body, {
        httpMetadata,
        // ETagは自動設定されるが、必要なら明示設定
        // httpEgt は読み取り専用なのでここでは設定しない
      });

      console.debug(`Replicated object to secondary: ${key}`);
    } catch (error) {
      console.error(`Failed to replicate object ${key}:`, error);
      // レプリケーション失敗は致命的ではないので例外は投げない
    }
  }

  /**
   * オブジェクトの削除をセカンダリにも反映
   */
  async replicateDeletion(key: string): Promise<void> {
    if (!this.enabled) return;

    try {
      await this.secondary.delete(key);
      console.debug(`Replicated deletion to secondary: ${key}`);
    } catch (error) {
      console.error(`Failed to replicate deletion ${key}:`, error);
    }
  }

  /**
   * バックグラウンドでレプリケーション状態を確認・修正
   * （実際にはCron Triggerで定期実行推奨）
   */
  async syncBucket(): Promise<{ replicated: number; failed: number }> {
    if (!this.enabled) return { replicated: 0, failed: 0 };

    let replicated = 0;
    let failed = 0;

    try {
      // プライマリバケットのオブジェクトをリスト
      let cursor: string | undefined;
      do {
        const list = await this.primary.list({ 
          cursor,
          limit: 1000 // ページサイズ
        });

        // 各オブジェクトについてレプリケーション状態確認
        for (const { key } of list.keys) {
          try {
            const primaryObj = await this.primary.get(key);
            const secondaryObj = await this.secondary.get(key);

            // セカンダリに存在しない場合はコピー
            if (!secondaryObj && primaryObj) {
              await this.replicateObject(key);
              replicated++;
            }
            // 両方に存在する場合はETag等で整合性チェック（省略可能）
          } catch (e) {
            failed++;
            console.error(`Sync error for ${key}:`, e);
          }
        }

        cursor = list.cursor;
      } while (cursor);

      return { replicated, failed };
    } catch (error) {
      console.error('Bucket sync failed:', error);
      return { replicated, failed };
    }
  }
}

/**
 * ファクトリ関数
 * 注意: 実際の使用では、wrangler.toml でセカンダリバケットを追加設定必要
 */
export function createR2Replication(env: Env): R2Replication {
  // セカンダリバケット用のバインディングが必要
  // 例: wrangler.toml に 
  # [[r2_buckets]]
  # binding = "BUCKET_SECONDARY"
  # bucket_name = "manual-processor-files-secondary"
  
  if (!env.BUCKET_SECONDARY) {
    console.warn('Secondary R2 bucket not configured, replication disabled');
    return new R2Replication(env.BUCKET, null as any, false);
  }

  return new R2Replication(env.BUCKET, env.BUCKET_SECONDARY);
}
```

**設定例 (wrangler.toml 追加)**:
```toml
# プライマリバケット（既存）
[[r2_buckets]]
binding = "BUCKET"
bucket_name = "manual-processor-files"

# セカンダリバケット（レプリケーション用）
[[r2_buckets]]
binding = "BUCKET_SECONDARY"
bucket_name = "manual-processor-files-secondary"
```

---

## ステップ3: アップロードフローにレプリケーション組み込み
**対象ファイル**: `src/routes/upload.ts`
- アップロード完了後にセカンダリバケットへレプリケーション
- メタデータはKVにのみ保存（KVにも同様のレプリケーション戦略が必要）

```typescript
import { createR2Replication } from '../lib/r2-replication';

// アップロード関数内部で
export function registerUploadRoutes(app: Hono<{ Bindings: Env }>) {
  // レプリケーター初期化（シングルトン推奨だが、ここではインラインで簡易実装）
  // 実際にはモジュールレベルで初期化するか、DIコンテナ使用
  const r2Replication = createR2Replication(c.env);

  app.post('/api/upload', async (c) => {
    try {
      // ... 既存のバリデーション・アップロード処理 unchanged

      // アップロード完了
      await c.env.BUCKET.put(key, arrayBuffer, {
        httpMetadata: {
          contentType: 'application/pdf'
        }
      });

      // 🔥 レプリケーション実行（ファイアアンドフォーゲット）
      // エラーでもアップロード自体は成功とする
      r2Replication.replicateObject(key).catch(err => {
        console.warn(`Replication failed for ${key}:`, err);
        // ここでアラート送信等も検討
      });

      // ... 既存のメタデータ保存処続
      const meta: UploadedFile = {
        fileId,
        filename,
        sizeMb: Math.round(file.size / 1024 / 1024 * 100) / 100,
        path: key,
        uploadedAt: new Date().toISOString()
      };

      await c.env.PROCESSING_KV.put(`uploaded:${fileId}`, JSON.stringify(meta));

      return c.json(meta);
    } catch (error) {
      // ... 既存エラーハンドリング unchanged
    }
  });
}
```

---

## ステップ4: KVレプリケーション戦略実装
**ファイル**: `src/lib/kv-replication.ts` (新規)
- KVのエクスポート/インポート機能を使用したバックアップ戦略
- Cron Triggerで定期実行推奨

```typescript
import type { Env } from '../lib/types';

export class KVReplication {
  constructor(
    private readonly kv: KVNamespace,
    private readonly bucket: R2Bucket,
    private readonly backupPrefix: string = 'kv-backups/'
  ) {}

  /**
   * KVネームスペースをR2バケットにバックアップ
   * 注意: 大規模KVの場合は制限あり（キー数・サイズ制限）
   */
  async backup(): Promise<{ 
    success: boolean; 
    backedUpCount: number; 
    totalCount: number;
    error?: string 
  }> {
    try {
      let total = 0;
      let backedUp = 0;
      let cursor: string | undefined;
      
      // KVをページングしながら処理
      do {
        const list = await this.kv.list({ 
          cursor,
          limit: 1000 // 安全なページサイズ
        });
        
        total += list.keys.length;
        
        // 各キーについてバックアップ
        for (const { key } of list.keys) {
          try {
            const value = await this.kv.get(key, 'text'); // または 'json' または 'arrayBuffer'
            if (value !== null) {
              const backupKey = `${this.backupPrefix}${Date.now()}-${key.replace(/[^\w\-]/g, '_')}`;
              await this.bucket.put(backupKey, value, {
                httpMetadata: {
                  contentType: 'application/json' // または適切なタイプ
                }
              });
              backedUp++;
            }
          } catch (e) {
            console.error(`Failed to backup KV key ${key}:`, e);
            // 個別の失敗は続行
          }
        }
        
        cursor = list.cursor;
      } while (cursor);

      return {
        success: true,
        backedUpCount: backedUp,
        totalCount: total
      };
    } catch (error) {
      return {
        success: false,
        backedUpCount: 0,
        totalCount: 0,
        error: error.message
      };
    }
  }

  /**
   * 特定のバックアップからKVを復元
   * 注意: これにより現在のKVが上書きされるため慎重に使用
   */
  async restoreFromBackup(backupTimestamp: string): Promise<{ success: boolean; error?: string }> {
    try {
      // バックアップファイルをリスト
      const list = await this.bucket.list({
        prefix: `${this.backupPrefix}${backupTimestamp}-`,
        limit: 10000
      });

      let restored = 0;
      
      for (const { key } of list.keys) {
        try {
          // ファイル名から元のKVキーを復元（簡易実装）
          const originalKey = key.substring(`${this.backupPrefix}${backupTimestamp}-`.length).replace(/_[^\w\-]+/g, '');
          
          const value = await this.bucket.get(key, 'text');
          if (value !== null) {
            await this.kv.put(originalKey, value);
            restored++;
          }
        } catch (e) {
          console.error(`Failed to restore KV key from ${key}:`, e);
        }
      }

      return {
        success: true,
        // restoredCount: restored など詳細情報も追加可能
      };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }
}

/**
 * ファクトリ関数
 */
export function createKVReplication(env: Env) {
  return new KVReplication(env.PROCESSING_KV, env.BUCKET);
}
```

**注意**: 
- KVの完全バックアップには制限があるため、実運用では重要なメタデータのみを対象にするか、
- 外部のバックアップサービスを検討する

---

## ステップ5: Cron Triggerによる自動バックアップ設定
**ファイル**: `wrangler.toml` 追加
```toml
# KVバックアップ用のCron Trigger
[[triggers]]
crons = ["0 2 * * *"]  # 毎日午前2時 UTC
```

**ハンドラー実装**: `src/index.ts` または別ファイルにスケジュールハンドラー追加
```typescript
import { createKVReplication } from './lib/kv-replication';

// グローバルレプリケーター（モジュールレベルで初期化）
const kvReplication = createKVReplication({
  BUCKET: process.env.BUCKET as any, // 実際には環境変数から取得する仕組みが必要
  PROCESSING_KV: process.env.PROCESSING_KV as any
} as Env);

export default {
  // ... 既存のfetchハンドラー unchanged

  /**
   * スケジュールハンドラー（Cron Trigger用）
   */
  async scheduled(event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
    console.log('Starting scheduled KV backup...');
    
    // 環境変数からレプリケーターを再構築（実際にはDIコンテナ推奨）
    const replication = createKVReplication(env);
    
    try {
      const result = await replication.backup();
      if (result.success) {
        console.log(`KV backup completed: ${result.backedUpCount}/${result.totalCount} keys backed up`);
      } else {
        console.error(`KV backup failed: ${result.error}`);
        // ここでアラート送信等も検討
      }
    } catch (error) {
      console.error('Scheduled backup error:', error);
    }
  }
};
```

**別実装アプローチ**: スケジュールハンドラー用の別エントリーポイント作成
- `src/scheduled.ts` を作成し、`wrangler.toml` で指定

---

## ステップ6: フェイルオーバー検出・切替メカニズム
**ファイル**: `src/lib/failover-manager.ts` (新規)
- プライマリ/セカンダリの健全性監視
- 自動フェイルオーバー（オプション、手動介入推奨も）

```typescript
import type { Env } from '../lib/types';

export class FailoverManager {
  constructor(
    private readonly env: Env,
    private readonly checkIntervalMs: number = 30000 // 30秒
  ) {
    this.isPrimaryHealthy = true;
    this.isSecondaryHealthy = true;
    this.failoverInProgress = false;
  }

  /**
   * R2バケットの健全性チェック
   */
  async checkR2Health(): Promise<{ primary: boolean; secondary: boolean }> {
    const healthCheckKey = `_health-check-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
    
    try {
      // プライマリチェック
      const startPrimary = Date.now();
      await this.env.BUCKET.put(healthCheckKey, 'health-check', {
        httpMetadata: { contentType: 'text/plain' }
      });
      await this.env.BUCKET.get(healthCheckKey);
      await this.env.BUCKET.delete(healthCheckKey);
      const primaryLatency = Date.now() - startPrimary;
      this.isPrimaryHealthy = primaryLatency < 5000; // 5秒以内なら健全
      
      // セカンダリチェック（設定されている場合）
      if (this.env.BUCKET_SECONDARY) {
        const startSecondary = Date.now();
        await this.env.BUCKET_SECONDARY.put(healthCheckKey, 'health-check', {
          httpMetadata: { contentType: 'text/plain' }
        });
        await this.env.BUCKET_SECONDARY.get(healthCheckKey);
        await this.env.BUCKET_SECONDARY.delete(healthCheckKey);
        const secondaryLatency = Date.now() - startSecondary;
        this.isSecondaryHealthy = secondaryLatency < 5000;
      } else {
        this.isSecondaryHealthy = false; // セカンダリ未設定
      }
      
      return { primary: this.isPrimaryHealthy, secondary: this.isSecondaryHealthy };
    } catch (error) {
      console.error('R2 health check failed:', error);
      return { primary: false, secondary: false };
    }
  }

  /**
   * KVネームスペースの健全性チェック
   */
  async checkKVHealth(): Promise<{ primary: boolean }> {
    const healthCheckKey = `_health-check-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
    
    try {
      const start = Date.now();
      await this.env.PROCESSING_KV.put(healthCheckKey, 'health-check');
      await this.env.PROCESSING_KV.get(healthCheckKey);
      await this.env.PROCESSING_KV.delete(healthCheckKey);
      const latency = Date.now() - start;
      return { primary: latency < 2000 }; // 2秒以内なら健全
    } catch (error) {
      console.error('KV health check failed:', error);
      return { primary: false };
    }
  }

  /**
   * ヘルスチェックループ開始
   * 注意: ワーカーインスタンスごとに動作するため、実際には別のワーカーか外部サービスで実行推奨
   */
  startHealthCheckLoop(): NodeJS.Timeout {
    return setInterval(async () => {
      try {
        const [r2Health, kvHealth] = await Promise.all([
          this.checkR2Health(),
          this.checkKVHealth()
        ]);
        
        // ヘルス状態変化をログ
        console.log(`Health check - R2: { primary: ${r2Health.primary}, secondary: ${r2Health.secondary} }, KV: { primary: ${kvHealth.primary} }`);
        
        // フェイルオーバー判定ロジック（簡易版）
        // 実際にはより複雑な判定と手動承認フローが必要
        if (!r2Health.primary && !this.failoverInProgress) {
          console.warn('Primary R2 unhealthy, considering failover...');
          // ここでアラート送信等
          // 自動フェイルオーバーはリスクがあるため、ここでは警告のみ
          // this.attemptFailover();
        }
      } catch (error) {
        console.error('Health check loop error:', error);
      }
    }, this.checkIntervalMs);
  }

  /**
   * フェイルオーバーを試行（実際の実装では慎重に）
   */
  async attemptFailover(): Promise<boolean> {
    if (this.failoverInProgress) return false;
    
    this.failoverInProgress = true;
    try {
      // ここでは単純に警告のみ。実際のフェイルオーバーは:
      // 1. アプリケーション設定を変更してセカンダリをプライマリとして使用
      // 2. DNSまたはロードバランサーの設定変更
      // 3. データの同期確認
      // これらはインフラストラクチャレベルでの操作が必要
      
      console.warn('Failover would require infrastructure changes (DNS, config updates, etc.)');
      return false; // 実際には実装しない
    } finally {
      this.failoverInProgress = false;
    }
  }

  /**
   * 現在のプライマリエンドポイントを取得（フェイルオーバー状況に応じて）
   * 実際のアプリケーションでは、このロジックを使って動的にエンドポイントを切替
   */
  getActiveR2Bucket(): R2Bucket {
    // 簡易実装: プライマリが健全ならプライマリ、そうでなければセカンダリ（あれば）
    if (this.isPrimaryHealthy && this.env.BUCKET) {
      return this.env.BUCKET;
    }
    if (this.isSecondaryHealthy && this.env.BUCKET_SECONDARY) {
      return this.env.BUCKET_SECONDARY;
    }
    // 両方不健全またはセカンダリ無しの場合はプライマリを返すが、エラーになるべき
    return this.env.BUCKET;
  }
}

/**
 * ファクトリ関数
 */
export function createFailoverManager(env: Env) {
  return new FailoverManager(env);
}
```

---

## ステップ7: ヘルスチェックエンドポイント拡張
**対象ファイル**: `src/routes/health.ts`
- ディープヘルスチェックを追加し、R2/KVの状態を確認

```typescript
import { FailoverManager } from '../lib/failover-manager';

// グローバルフェイルオーバーマネージャー（実際には適切なスコープで管理）
let failoverManager: FailoverManager | null = null;

export function registerHealthRoutes(app: Hono<{ Bindings: Env }>) {
  app.get('/api/health', (c) => {
    const response: HealthResponse = {
      status: 'ok',
      version: '2.0.0',
      processorType: 'cloudflare-workers'
    };
    return c.json(response);
  });

  /**
   * ディープヘルスチェック - ストレージと外部サービスの状態確認
   */
  app.get('/api/health/deep', async (c) => {
    try {
      // 初回のみフェイルオーバーマネージャー初期化
      if (!failoverManager) {
        failoverManager = createFailoverManager(c.env);
      }

      const [r2Health, kvHealth] = await Promise.all([
        failoverManager.checkR2Health(),
        failoverManager.checkKVHealth()
      ]);

      const isHealthy = r2Health.primary && kvHealth.primary;

      return c.json({
        status: isHealthy ? 'healthy' : 'degraded',
        timestamp: new Date().toISOString(),
        checks: {
          r2: {
            primary: r2Health.primary,
            secondary: r2Health.secondary,
            message: r2Health.primary && r2Health.secondary 
              ? 'Both primary and secondary healthy'
              : !r2Health.primary && !r2Health.secondary
                ? 'Both primary and secondary unhealthy'
                : !r2Health.primary
                  ? 'Primary unhealthy'
                  : 'Secondary unhealthy'
          },
          kv: {
            primary: kvHealth.primary,
            message: kvHealth.primary ? 'Healthy' : 'Unhealthy'
          }
        }
      }, isHealthy ? 200 : 503); // サービス利用不可時は503
    } catch (error) {
      console.error('Deep health check error:', error);
      return c.json(
        { 
          status: 'unhealthy', 
          error: 'Health check failed',
          timestamp: new Date().toISOString() 
        }, 
        500
      );
    }
  });

  /**
   * フェイルオーバー状況確認エンドポイント（運用用）
   */
  app.get('/api/health/failover-status', async (c) => {
    if (!failoverManager) {
      return c.json({ error: 'Failover manager not initialized' }, 503);
    }
    
    // 実際のフェイルオーバーマネージャーから状態取得
    // ここでは簡易的にプロパティ公開（実際にはゲッターメソッド必要）
    return c.json({
      timestamp: new Date().toISOString(),
      primaryR2Healthy: failoverManager['isPrimaryHealthy'],
      secondaryR2Healthy: failoverManager['isSecondaryHealthy'],
      failoverInProgress: failoverManager['failoverInProgress'],
      activeR2Bucket: failoverManager.getActiveR2Bucket() === c.env.BUCKET ? 'primary' : 
                       failoverManager.getActiveR2Bucket() === c.env.BUCKET_SECONDARY ? 'secondary' : 'unknown'
    });
  });
}
```

---

## ステップ8: バックアップ・リストア手順ドキュメント化
**ファイル**: `docs/operational/backup-restore.md` (新規)
- 日次KVバックアップ手順（Cron Trigger利用）
- R2レプリケーション状況確認方法
- 災害発生時のリストア手順
- RTO（復旧時間目標）とRPO（復旧点目標）の定義
- 定期的なリストア訓練の推奨

**RTO/RPO目標例**:
- RPO (Recovery Point Objective): 1時間（最大1時間のデータ損失許容）
- RTO (Recovery Time Objective): 30分（30分以内にサービス復旧）

---

## ステップ9: 監視・アラート設定ガイド
**ファイル**: `docs/operational/monitoring-alerts.md` (新規)
- ヘルスチェックエンドポイントの外部監視設定（UptimeRobot等）
- レプリケーションラグの監視
- ストレージ使用量のアラート
- 異常なエラーレートの検出
- Cloudflare Logs と 外部SIEM連携

**推奨アラート**:
- ヘルスチェックエンドポイントが5連続で失敗
- R2使用量が80%を超過
- KVレプリケーションバックアップ失敗
- 5xxエラー率が1%を超過（5分間隔）

---

## 完了条件
- [ ] R2マルチリージョン設定またはアプリケーションレベルレプリケーション実装
- [ ] KVバックアップ戦略（Cron Triggerによる自動バックアップ）実装
- [ ] アップロードフローにセカンダリR2へのレプリケーション組み込み
- [ ] ヘルスチェックエンドポイント `/api/health/deep` が実装済み
- [ ] フェイルオーバー状況確認エンドポイント `/api/health/failover-status` が実装済み
- [ ] バックアップ・リストア手順がドキュメント化済み
- [ ] 監視・アラート設定ガイドが完成
- [ ] テストでレプリケーション・ヘルスチェック・フェイルオーバーロジック網羅（モック使用）