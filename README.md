# 氣候行動學習互動網站

依照《氣候行動完整功能規格書 v2》建立，目前完成規格書第 10 節「建議推進順序」第 1～2 步：資料庫 schema ＋ LINE webhook 基本收發（含 school 參數判斷），以及每日推送＋答題＋積分/streak/徽章核心邏輯。另外額外做了 Rich Menu（基本資料／目前狀態／環保打卡／排行榜）、暱稱設定、拍照打卡送能量（老師審核制）。

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

建立/更新資料庫 schema（用 Alembic migration，見下方「資料庫 schema 變更（Alembic）」一節）：

```powershell
alembic upgrade head
```

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

- `schools / students / questions / answer_logs / assessment_responses / daily_pushes` 六張表（`app/models.py`），對應規格書第 2 節設計；`daily_pushes` 是新增的推送紀錄表，用來決定下一次要推哪一題、避免同一天重複推送
- LINE webhook（`app/routers/webhook.py`）：
  - `follow` 事件：學生加好友時建立 `students` 資料；若加好友連結有帶 `school` 參數則自動歸校，否則以 Quick Reply 按鈕請學生手動選擇學校（規格書第 3 節的保險機制）
  - `postback` 事件：處理學生點選學校按鈕後的歸校，以及點選測驗選項後的答題（`answer|question_id|option_index` 格式）
  - 文字訊息：若尚未歸校則詢問學校，已歸校則回覆目前身分／能量／連續天數／徽章
- 每日推送＋答題＋積分/streak/徽章（規格書第 10 節第 2 步）：
  - `app/scheduler.py`：程式啟動時用 APScheduler 在背景排程，每天 Asia/Taipei 08:00 自動推送當日題目（`push_daily_question`）
  - `app/daily_push.py`：取出「`scheduled_date` 已到（`<=` 今天）、但還沒推送過」的下一題（`app/crud.get_next_unpushed_question`），用 LINE Broadcast API 一次推給所有好友（知識卡 + 測驗，測驗選項做成 Quick Reply 按鈕）；同一天已推送過就不會再推。沒有設定 `scheduled_date` 的題目不會被自動排程選到。用 `<=` 而不是 `==` 是為了在服務曾經漏推（例如 Render 休眠跳過某一天）時能自動補推；排定日期落在週末、或兩個 Round 之間的空檔週，當天就不會有題目符合條件，會自動跳過不推送
  - 學生點選答案後（`app/routers/webhook.py` 的 `_handle_answer_postback`）：寫入 `answer_logs`（同一題只能答一次），更新 `students.total_points / current_streak / longest_streak / badges`
  - `app/game_rules.py`：積分／連續天數／徽章／稱號的規則都集中在這裡（規格書沒有寫死細節，這是我先訂的一版合理規則，可依需求調整數值）：
    - 答對 +10、答錯 +2（給少量參與分數鼓勵持續作答）
    - 連續天數：以 Asia/Taipei 的日期為準，今天已經答過就不重複累計、昨天有答則 +1、中間斷過則歸 1 重新開始
    - 故事線：學生是「氣候行動守護者」，依累積能量從 🌱 幼苗守護者 → 🌿 綠芽行動家 → 🌳 森林守護者 → 🌍 地球衛士 → ⭐ 氣候英雄 逐步升級，每個階段都有對應的故事文案
    - 徽章：首次答題／首次答對／連續 3、7、30 天／累計答對 10、30 題／累積能量達 300，達成條件就解鎖，回覆訊息會附上「解鎖新徽章」提示
  - 手動測試用：`POST /admin/push-daily`（帶 `X-Admin-Key`，可加 `?force=true` 略過「今天已推送過」的檢查）可以不用等到 08:00 就手動觸發一次推送
  - `python -m scripts.seed_question` 可以建立一筆測試題目，方便本機測試整套流程
  - `python -m scripts.seed_questions_from_csv <csv路徑>` 用來批次匯入正式題庫，CSV 欄位為 `knowledge_card_text, question_text, option_a, option_b, option_c, option_d, correct_option, topic_tag, scheduled_date`（`correct_option` 填選項文字本身；`scheduled_date` 就是題目實際會被推送的日期，見上方「每日推送」小節）；已存在相同 `question_text` 的題目會自動跳過，可重複執行
  - **Render 免費方案休眠備援**：`.github/workflows/daily-push.yml` 用 GitHub Actions 排程（`cron: "0 0 * * *"`，即 Asia/Taipei 08:00）每天呼叫一次 `/admin/push-daily`。這個 HTTP 請求本身會把休眠中的 Render 服務叫醒，跟服務內建的 APScheduler 是雙保險：`push_daily_question` 有「今天已經推送過就跳過」的檢查，兩邊前後都觸發到也不會重複推送。需要在 GitHub repo 的 **Settings → Secrets and variables → Actions** 新增一個 secret：`ADMIN_API_KEY`，值要跟 Render 上的 `ADMIN_API_KEY` 一致（之後如果在 Render 換了 key，這裡也要跟著更新，否則 workflow 會收到 401）。GitHub Actions 的排程時間不保證精準觸發，尖峰時段可能延遲，但對「每天推 1 題」這種用途影響不大

## Rich Menu ＋ 暱稱 ＋ 環保打卡 ＋ 排行榜

- `python -m scripts.setup_rich_menu`：產生一張 2500x1686、2x2 四宮格的選單圖片（`Pillow` 畫的，用 Windows 內建的微軟正黑體 `msjh.ttc`），建立 LINE Rich Menu、上傳圖片、設成所有好友的預設選單。重複執行會先刪除同名舊選單再建新的，之後要改文案/版面直接改 `scripts/setup_rich_menu.py` 的 `CELLS` 重跑即可。四個按鈕都是 `menu|xxx` 格式的 PostbackAction，由 `app/routers/webhook.py` 的 `_handle_menu_postback` 處理：
  - `基本資料`：回覆就讀學校
  - `目前狀態`：回覆身分／能量／連續天數／徽章（跟文字訊息查詢共用 `_status_text`）
  - `環保打卡`：回覆打卡說明（實際打卡是直接傳照片，不是點按鈕）
  - `排行榜`：回覆該校前 10 名（暱稱＋能量）
- 暱稱設定：學生選完學校後，下一則文字訊息會被當成暱稱存起來（`students.nickname`），設定前選單功能會提示要先設定暱稱。暱稱只存在我們資料庫，跟 LINE 顯示名稱無關，目的是排行榜不曝露 LINE 身份。
- 環保打卡（`app/eco_checkin.py` + `students` 傳圖片訊息）：學生傳照片給 bot → 用 LINE Blob API 下載原圖 → 用 Pillow 壓縮成長邊 ≤1000px、JPEG quality 70 → 存進新的 `eco_checkins` 表（`status="pending"`）。**設計上刻意先審核再發能量**：
  - `GET /admin/checkins?status=pending`（帶 `X-Admin-Key`）：列出待審核打卡，含 `image_url` 可直接開圖
  - `GET /admin/checkins/{id}/image`：回傳圖片本身，因為要給老師直接在瀏覽器開連結看照片，所以這個端點例外允許用網址參數 `?admin_key=` 代替 Header（其他 admin 端點都只認 Header）——僅限這個用途，網址會留在瀏覽器歷史/伺服器 log，不要外流
  - `POST /admin/checkins/{id}/approve`（可帶 `?points=`，預設 `game_rules.ECO_CHECKIN_POINTS=15`）：發放能量、檢查是否解鎖 `eco_first`／`eco_10` 徽章，並用 LINE Push Message 通知學生
  - `POST /admin/checkins/{id}/reject`：標記未通過，Push 通知學生可以再試一次
  - 打卡目前**不影響**每日答題的連續天數（streak 只跟每日測驗有關）
- **這只是「碳足跡計算器」裡「拍照打卡送分」的 bonus 版**；真正會計算數值的碳足跡問卷（規格書時程表 W2-3 上線那條線）還沒做，之後要做再另外討論

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

**注意**：`render.yaml` 已改用 Render 提供的免費 PostgreSQL（`databases` 區塊，`DATABASE_URL` 會自動指到這個資料庫），資料庫本身跟 Web Service 分開，服務休眠喚醒不會清空資料。但 Render 免費 PostgreSQL 有 90 天期限，到期需要升級或重建。免費方案 Web Service 閒置一段時間會休眠，第一個請求可能要等數十秒喚醒，LINE 平台通常會重試 webhook，不影響功能但體驗上第一次互動可能稍慢。

（本專案一開始用本機 SQLite 起步是延續規格書第 7 節的建議，但實測發現 Render 免費方案的 Web Service 檔案系統在服務休眠喚醒時會重置，SQLite 檔案跟著消失，所以提早換成 PostgreSQL；本機開發若不想裝 PostgreSQL，`DATABASE_URL` 留空或設回 `sqlite:///./climate_action.db` 仍可用 SQLite。）

## 尚未完成（規格書第 10 節後續步驟）

1. 成效評估問卷（LIFF 表單）＋排程推送（下一個要做的項目；需要先在 LINE Developers Console 建立 LIFF App）
2. 教師後台（總覽、個別學生頁、題目分析、成效總覽；目前只有 `/admin/checkins` 系列陽春 API，沒有網頁介面）
3. 真正的碳足跡計算器（問卷式計算數值，目前只有拍照打卡送分的 bonus 版）
4. 目前 30 題正式題庫已依實際行程排定 `scheduled_date`：9/14（一）那週是前測週，不推送題目；Round1 為 9/21（一）起連續 3 週的週一到週五（共 15 天，9/21~10/9，中間沒有空檔週）→ question_id 2~16；Round2 為 10/12（一）起同樣連續 3 週的週一到週五（共 15 天，10/12~10/30）→ question_id 17~31，10/12 當天同步進行中測（題庫本身沒有涵蓋，屬另外的評估問卷）；11/3 那週為 Round3 後測，題庫本身也沒有涵蓋（前測／中測／後測問卷屬於上方第 1 點「成效評估問卷」，還沒開發）。Round2 結束後題庫即用完，`push_daily_question` 會記 log（info 等級）、不會再推送，之後如果要延伸內容需要追加新題目並設定 `scheduled_date`（用 `scripts/seed_questions_from_csv.py` 匯入即可）

## 資料庫 schema 變更（Alembic）

專案已導入 [Alembic](https://alembic.sqlalchemy.org/) 管理資料庫 schema，取代原本 `Base.metadata.create_all()` 的作法。

> **背景**：先前 `students` 表新增 `nickname` 欄位時，因為 `create_all()` 只會建立「還不存在」的新表、**不會**幫已存在的表補欄位，導致本機 schema 跟 Render 上（已有真實資料的）Postgres 產生落差，上線後查詢 `students` 會直接噴 `UndefinedColumn` 錯誤。改用 Alembic 之後，每次改 `app/models.py` 都會產生一支對應的 migration script，用 `alembic upgrade head` 套用，本機、Render 兩邊的 schema 才會確實同步。

**修改 schema 的流程**：

1. 改 `app/models.py`
2. 產生 migration：`alembic revision --autogenerate -m "說明這次改了什麼"`（會依目前 DB 與 model 的差異，在 `alembic/versions/` 產生一支新檔案，**務必打開檢查**產生的內容是否符合預期，autogenerate 不是 100% 準確）
3. 本機套用：`alembic upgrade head`
4. commit migration 檔案一起 push
5. Render 部署時 `startCommand`（見 `render.yaml`）會自動先跑 `alembic upgrade head` 再啟動服務，正式環境的 schema 會跟著更新，不用手動操作

`alembic/env.py` 已設定成沿用 `app.config.settings.database_url`，本機 sqlite、Render Postgres 都不用另外調整連線設定。

## 關於加好友連結帶入學校參數

LINE 官方並未正式保證一般「加好友連結」（`https://line.me/R/ti/p/@BotID`）能把自訂查詢參數透過 `follow` webhook 事件傳回後端——這點規格書第 3 節也有提到，所以本專案把「加好友後跳出按鈕選單讓學生手動選學校」做成主要、可靠的機制，`school` 參數的自動判斷則是加分項（讀不到也不影響流程）。之後如果要做到「連結一點就自動歸校、完全不用手動選」，建議改用每校專屬的 LIFF 頁面作為入口，這是後續可以再討論的方向。
