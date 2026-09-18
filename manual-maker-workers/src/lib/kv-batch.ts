import type { Env } from '../lib/types';

export class KVBatch {
  constructor(private readonly kv: KVNamespace, private readonly env: Env) {}

  /**
   * 複数キーを並列取得
   * @param keys 取得したいキーの配列
   * @returns キーと値のマップ（存在しないキーは undefined）
   */
  async getMany<T = unknown>(keys: string[]): Promise<Record<string, T | undefined>> {
    const promises = keys.map(key => this.kv.get<T>(key, 'json'));
    const results = await Promise.all(promises);
    return Object.fromEntries(keys.map((key, i) => [key, results[i] ?? undefined]));
  }

  /**
   * プレフィックス一致キーの一括取得（list + 並列get）
   * @param prefix 検索プレフィックス
   * @param limit 最大取得件数（省略時は1000）
   * @returns キーと値のマップ
   */
  async getByPrefix<T = unknown>(prefix: string, limit?: number): Promise<Record<string, T>> {
    const list = await this.kv.list({ prefix, limit: limit ?? 1000 });
    if (!list.keys.length) return {};

    const promises = list.keys.map(key => this.kv.get<T>(key.name, 'json'));
    const results = await Promise.all(promises);
    const result: Record<string, T> = {};
    list.keys.forEach((key, i) => {
      const value = results[i];
      if (value !== null) {
        result[key.name] = value;
      }
    });
    return result;
  }

  /**
   * 複数キーを並列保存
   * @param entries キーと値のペア配列
   */
  async setMany(entries: { key: string; value: unknown; expirationTtl?: number }[]) {
    const promises = entries.map(({ key, value, expirationTtl }) =>
      this.kv.put(key, JSON.stringify(value), { expirationTtl })
    );
    await Promise.all(promises);
  }

  /**
   * 複数キーを並列削除
   * @param keys 削除したいキーの配列
   */
  async deleteMany(keys: string[]) {
    const promises = keys.map(key => this.kv.delete(key));
    await Promise.all(promises);
  }
}

/**
 * KVBatchインスタンス作成ヘルパー
 */
export function createKVBatch(env: Env) {
  return new KVBatch(env.PROCESSING_KV, env);
}