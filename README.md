# Linux Service Health Check

這個專案會監控 Linux 上的 systemd 服務名稱，當服務異常時依照條件寄出告警信件，並在符合條件時自動重啟服務。支援 SendGrid（預設）與 SMTP（例如 Gmail）。

## 功能重點

- 監控 systemd 服務（例如 `n8n.service`）
- 每個服務可設定自己的監控頻率、告警次數、重啟次數
- 服務恢復時只寄一次「恢復通知」
- 支援重啟後執行自訂指令（例如 `docker compose up -d`）
- 使用 systemd service + timer 部署

## 專案結構

```
.
├── src/monitor.py
├── examples/config.json
├── systemd/service-monitor.service
├── systemd/service-monitor.timer
└── .env.example
```

## 設定檔

### 1) 建立設定資料夾

```bash
sudo mkdir -p /etc/service-monitor
sudo mkdir -p /var/lib/service-monitor
```

### 2) 設定 `config.json`

複製範例並依需求修改（監控 `n8n.service` 與 `nginx.service` 範例）：

```bash
sudo cp examples/config.json /etc/service-monitor/config.json
```

`config.json` 範例欄位說明：

- `email_provider`: `sendgrid` 或 `smtp`
- `state_path`: 狀態檔路徑，用來記錄連續失敗次數與告警狀態
- `services`: 以 systemd 服務名稱為 key
  - `check_interval_seconds`: 監控頻率（秒）
  - `failures_before_restart`: 連續失敗幾次後自動重啟
  - `failures_before_alert`: 連續失敗幾次後寄送告警
  - `post_restart_commands`: 重啟後額外要執行的指令（可留空）

### 3) 設定 `.env`

```bash
sudo cp .env.example /etc/service-monitor/.env
sudo nano /etc/service-monitor/.env
```

- **SendGrid (預設)**
  - `SENDGRID_API_KEY`
  - `SENDGRID_FROM`
  - `SENDGRID_TO`
- **SMTP (Gmail 範例)**
  - `SMTP_HOST`、`SMTP_PORT`
  - `SMTP_USER`、`SMTP_PASSWORD`
  - `SMTP_FROM`、`SMTP_TO`
  - `SMTP_TLS=true`

## 部署與運行

### 1) 放置程式

```bash
sudo mkdir -p /opt/service-monitor
sudo cp -R src /opt/service-monitor/
```

### 2) 安裝 systemd unit

```bash
sudo cp systemd/service-monitor.service /etc/systemd/system/service-monitor.service
sudo cp systemd/service-monitor.timer /etc/systemd/system/service-monitor.timer
sudo systemctl daemon-reload
```

### 3) 啟動 timer

```bash
sudo systemctl enable --now service-monitor.timer
```

### 4) 觀察狀態

```bash
systemctl status service-monitor.timer
journalctl -u service-monitor.service -f
```

## 重要行為說明

- 當服務連續失敗達到 `failures_before_restart` 時，會執行 `systemctl restart <service>`，並執行 `post_restart_commands`。
- 當服務連續失敗達到 `failures_before_alert` 時，會寄出告警信件（只寄一次）。
- 當服務恢復為正常狀態時會寄出「恢復通知」（只寄一次）。

## 手動執行

```bash
python3 src/monitor.py --config /etc/service-monitor/config.json --env /etc/service-monitor/.env
```
