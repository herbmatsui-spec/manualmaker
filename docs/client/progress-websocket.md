# クライアントサイド WebSocket 接続ガイド

このドキュメントでは、Manual Maker の進捗更新を受信するための WebSocket 接続方法について説明します。

## 接続手順

1. ファイルIDを取得し、WebSocket エンドポイントに接続します。
2. 接続後にサーバーから現在の進捗状況が送信されます。
3. その後、進捗更新がリアルタイムで送信されます。
4. 接続が切れた場合は、指数バックオフを用いて再接続を試みます。

## サンプルコード (JavaScript)

```javascript
class ProgressClient {
  constructor(fileId, onUpdate, onError) {
    this.fileId = fileId;
    this.onUpdate = onUpdate;
    this.onError = onError;
    this.ws = null;
    this.retryCount = 0;
    this.maxRetryDelay = 30000; // 30秒
    this.baseDelay = 1000; // 1秒
  }

  connect() {
    const url = `wss://${location.host}/api/progress/${this.fileId}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.retryCount = 0; // 接続成功時にリトライカウントをリセット
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.onUpdate(data);
      } catch (e) {
        console.error('Failed to parse progress message:', e);
        this.onError(e);
      }
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.scheduleReconnect();
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.onError(error);
    };
  }

  scheduleReconnect() {
    // 指数バックオフ: baseDelay * 2^retryCount, 최대 maxRetryDelay
    const delay = Math.min(
      this.baseDelay * Math.pow(2, this.retryCount),
      this.maxRetryDelay
    );
    this.retryCount++;

    console.log(`Scheduling reconnect in ${delay}ms (attempt ${this.retryCount})`);
    setTimeout(() => {
      this.connect();
    }, delay);
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

// 使用例
const fileId = 'your-file-id-here';
const progressClient = new ProgressClient(
  fileId,
  (progress) => {
    // UI を更新
    document.getElementById('progress-bar').value = progress.progress;
    document.getElementById('progress-text').textContent = `${progress.stage} (${progress.progress}%)`;
  },
  (error) => {
    console.error('Progress error:', error);
    // エラー表示など
  }
);

// 接続開始
progressClient.connect();

// ページアンロード時に切断
window.addEventListener('beforeunload', () => {
  progressClient.disconnect();
});
```

## HTTP フォールバック (ポーリング)

WebSocket が利用できない環境では、HTTP エンドポイントをポーリングすることで進捗を取得できます。

```javascript
class ProgressPoller {
  constructor(fileId, onUpdate, onError, interval = 2000) {
    this.fileId = fileId;
    this.onUpdate = onUpdate;
    this.onError = onError;
    this.interval = interval;
    this.timer = null;
  }

  start() {
    this.fetchProgress();
    this.timer = setInterval(() => {
      this.fetchProgress();
    }, this.interval);
  }

  async fetchProgress() {
    try {
      const response = await fetch(`/api/progress/${this.fileId}/http`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      if (data) {
        this.onUpdate(data);
      }
    } catch (error) {
      console.error('Failed to fetch progress:', error);
      this.onError(error);
    }
  }

  stop() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
}

// 使用例
const fileId = 'your-file-id-here';
const poller = new ProgressPoller(
  fileId,
  (progress) => {
    // UI を更新
    document.getElementById('progress-bar').value = progress.progress;
    document.getElementById('progress-text').textContent = `${progress.stage} (${progress.progress}%)`;
  },
  (error) => {
    console.error('Progress poll error:', error);
  },
  2000 // 2秒間隔
);

// ポーリング開始
poller.start();

// ページアンロード時に停止
window.addEventListener('beforeunload', () => {
  poller.stop();
});
```

## エラーハンドリング

- WebSocket 接続失敗時は、指数バックオフを用いて自動的に再接続を試みます。
- 一定回数以上の再試行失敗後は、HTTP フォールバックに切り替えることを検討してください。
- メッセージのパースエラーが発生した場合は、コンソールにエラーを出力し、必要に応じてユーザーに通知してください。

## セキュリティ注意点

- WebSocket 接続は常に WSS (WebSocket Secure) を使用してください。
- 本番環境では、適切なオリジンチェックを行うことをお勧めします（ただし、当実装では Cloudflare Workers が提供するセキュリティに依存しています）。