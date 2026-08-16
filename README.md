# 氣候行動學習互動網站

依照《氣候行動完整功能規格書 v2》建立，目前完成規格書第 10 節「建議推進順序」第 1 步：資料庫 schema ＋ LINE webhook 基本收發（含 school 參數判斷）。

## 環境設定

使用 Anaconda 建立的專屬環境 `climate-bot`（Python 3.11，位於 `D:\anaconda3\envs\climate-bot`）：

```powershell
conda activate climate-bot
pip install -r requirements.txt
Copy-Item .env.example .env
```

若尚未建立這個環境：`conda create -y -n climate-bot python=3.11`

（若你的 PowerShell 沒有設定 `conda activate`，可以改用完整路徑呼叫，例如：`D:\anaconda3\envs\climate-bot\python.exe -m uvicorn app.main:app --reload`）

編輯 `.env`，填入你的 LINE Messaging API channel secret / access token（LINE Developers Console → Messaging API 頁籤取得）。

## 建立第一間學校

```powershell
python -m scripts.seed_school "南投高中" nantou_high
```

會建立 `schools` 資料並印出該校專屬加好友連結。

## 本機啟動

```powershell
uvicorn app.main:app --reload
```

啟動後 webhook 端點為 `http://localhost:8000/webhook`。本機測試需要用 ngrok（或類似工具）把這個網址對外公開，再到 LINE Developers Console 的 Messaging API 設定頁把 Webhook URL 設成 `https://<你的ngrok網址>/webhook` 並啟用 Webhook。

## 目前功能

- `schools / students / questions / answer_logs / assessment_responses` 五張表（`app/models.py`），對應規格書第 2 節設計
- LINE webhook（`app/routers/webhook.py`）：
  - `follow` 事件：學生加好友時建立 `students` 資料；若加好友連結有帶 `school` 參數則自動歸校，否則以 Quick Reply 按鈕請學生手動選擇學校（規格書第 3 節的保險機制）
  - `postback` 事件：處理學生點選學校按鈕後的歸校
  - 文字訊息：若尚未歸校則詢問學校，已歸校則回覆目前積分／連續天數／徽章（先用資料庫現有欄位回覆，尚未接上每日推送與答題邏輯）

## 管理用 API（暫時性，用於雲端環境沒有 Shell 可下指令時建立學校）

`POST /admin/schools`、`GET /admin/schools`，需帶 Header `X-Admin-Key: <ADMIN_API_KEY>`。範例：

```
POST https://climate-action-bot.onrender.com/admin/schools
Header: X-Admin-Key: <你的 ADMIN_API_KEY>
Body: {"school_name": "南投高中", "join_link_code": "nantou_high"}
```

之後有正式教師後台可以管理學校資料時，這個端點可以移除。

## 部署到 Render（測試用）

專案根目錄已附 `render.yaml`，可用 Render 的 Blueprint 功能一鍵建立服務：

1. 到 [Render Dashboard](https://dashboard.render.com) → New → Blueprint，選這個 GitHub repo
2. Render 會讀取 `render.yaml` 自動建立 Web Service，建置指令與啟動指令都已寫好
3. 部署頁面會要求填入標記 `sync: false` 的環境變數：`LINE_CHANNEL_SECRET`、`LINE_CHANNEL_ACCESS_TOKEN`（值同你本機 `.env` 內的內容）
4. 部署完成後會拿到一個固定網址，例如 `https://climate-action-bot.onrender.com`
5. 到 LINE Developers Console → Messaging API 頁籤，把 Webhook URL 設成 `https://climate-action-bot.onrender.com/webhook`，按 Verify 確認成功，並開啟「Use webhook」

**注意**：Render 免費方案的檔案系統是暫存的（每次重新部署或服務休眠喚醒都可能清空），目前用的 SQLite 資料庫在免費方案上不適合長期保存正式資料，僅供功能測試；之後正式上線前建議換成 Render 提供的 PostgreSQL（免費方案有時數限制）或其他持久化資料庫。免費方案服務閒置一段時間會休眠，第一個請求可能要等數十秒喚醒，LINE 平台通常會重試 webhook，不影響功能但體驗上第一次互動可能稍慢。

## 尚未完成（規格書第 10 節後續步驟）

1. 每日推送＋答題＋積分/streak/徽章核心邏輯（目前欄位已建好但沒有寫入邏輯）
2. 成效評估問卷（LIFF 表單）＋排程推送
3. 教師後台（總覽、個別學生頁、題目分析、成效總覽）
4. 排程任務（cron）：每日推送、依週次觸發成效評估

## 關於加好友連結帶入學校參數

LINE 官方並未正式保證一般「加好友連結」（`https://line.me/R/ti/p/@BotID`）能把自訂查詢參數透過 `follow` webhook 事件傳回後端——這點規格書第 3 節也有提到，所以本專案把「加好友後跳出按鈕選單讓學生手動選學校」做成主要、可靠的機制，`school` 參數的自動判斷則是加分項（讀不到也不影響流程）。之後如果要做到「連結一點就自動歸校、完全不用手動選」，建議改用每校專屬的 LIFF 頁面作為入口，這是後續可以再討論的方向。
