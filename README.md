# 🎵 Vibe Coding 專案追蹤站

追蹤各種用 AI / Vibe Coding 完成的專案，不限 APP、WEB、LINE BOT、API。

👉 **[線上版](https://mtsung.github.io/vibe_coding_tracker/)**

## 新增專案

編輯 `data.json`，照格式加一筆：

```json
{
  "name": "專案名稱",
  "type": "WEB",
  "description": "簡短描述",
  "url": "專案連結",
  "checkUrl": "",
  "source": "Threads",
  "sourceUrl": "https://...",
  "date": "2026-04-05",
  "deadDate": "",
  "tags": ["tag1", "tag2"]
}
```

| 欄位 | 說明 |
|------|------|
| `name` | 專案名稱 |
| `type` | 類型：`APP` / `WEB` / `LINE BOT` / `API` / 自訂 |
| `description` | 簡短描述 |
| `url` | 專案連結 |
| `checkUrl` | 健康檢查用的 URL（選填，APP 填商店連結，空白則用 `url`） |
| `source` | 在哪裡看到的 |
| `sourceUrl` | 來源原始連結 |
| `date` | 發現日期 |
| `deadDate` | 死亡日期（留空 = 存活中，由 GitHub Action 自動填入） |
| `tags` | 標籤 |

## 自動健康檢查

每天台灣時間 10:00，GitHub Action 會自動檢查所有專案：

- **WEB / API**：HTTP 請求，4xx / 5xx / 連不上 → 標記死亡
- **APP**：抓 App Store / Google Play 頁面，偵測下架關鍵字
- **LINE BOT**：跳過（無法自動檢查）
- 死掉的專案如果隔天又活了，會自動復活

## 歡迎發 PR

看到什麼有趣的 vibe coding 專案，歡迎直接編輯 `data.json` 發 PR。
