# Deployment

## ローカル開発

```bash
python -m uvicorn src.web.app:app --reload --host 127.0.0.1 --port 8000
```

## 本番 (systemd)

`/etc/systemd/system/manual-processor.service`:

```ini
[Unit]
Description=Manual Processor Web
After=network.target

[Service]
WorkingDirectory=/opt/manual_processor
EnvironmentFile=/opt/manual_processor/.env
ExecStart=/opt/manual_processor/venv/bin/python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000
Restart=on-failure
User=manualproc

[Install]
WantedBy=multi-user.target
```

## Docker (推奨)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t manual-processor .
docker run -p 8000:8000 --env-file .env manual-processor
```

## 観測性

Prometheus 形式で `/metrics` を公開。Grafana ダッシュボードの例:

- ジョブスループット: `rate(manual_processor_jobs_total[5m])`
- 平均処理時間: `rate(manual_processor_job_duration_seconds_sum[5m]) / rate(manual_processor_job_duration_seconds_count[5m])`
- APIエラー率: `rate(manual_processor_api_errors_total[5m])`

## セキュリティチェックリスト

- [ ] HTTPS 終端(リバースプロキシ)
- [ ] CORS をワイルドカードにしない
- [ ] API キーを `.env` で管理し、リポジトリに含めない
- [ ] アップロードサイズ上限を設定 (`web_upload_max_mb`)
- [ ] 監査ログを別ボリュームに永続化