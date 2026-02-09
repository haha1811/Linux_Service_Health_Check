# Changelog
本專案所有重要變更都會記錄在此檔案。

格式採用 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，
版本規範採用 [Semantic Versioning](https://semver.org/lang/zh-TW/).

## [0.1.0] - 2026-02-09
### Added
- 支援 systemd 服務監控、告警與恢復通知。
- 支援本機 TCP port 監控（例如 80、5678），可設定告警與重啟指令。
- 支援 SendGrid（預設）與 SMTP 寄信。
- 提供 systemd service + timer 部署方式。
- 新增版本檔 `VERSION`。

### Fixed
- 只有在曾寄出告警後才會寄出恢復通知。
- 時間欄位預設改為台北時區（Asia/Taipei），可在設定檔切換 UTC。

### Documentation
- 補充部署與升級流程說明。
