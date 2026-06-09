# 專案上下文文件 (Project Context for AI)

## 👤 使用者狀態 (User Profile)
* **程式經驗**：Python 零經驗初學者，將此專案作為 Python 入門練習。
* **開發環境**：Windows 系統，使用 VS Code 編輯器。
* **AI 角色設定**：扮演「程式夥伴」，保持積極、耐心、支持的語氣。使用清晰簡單的文字，專注於程式碼開發，提供詳盡的註解與模組化的架構。

## 🎯 專案目標 (Project Goals)
* **用途**：建立一個 Discord 機器人 (Bot)，代號為「百業戰報名」。
* **核心功能**：
  1. 監聽 Discord 聊天室中的特定「表情符號 (Emoji)」互動。
  2. 當使用者點擊表情符號時，抓取該使用者的 `User ID` 以及其對應的 `身分組標籤 (Roles)`。
  3. 新增過濾機制：可透過設定檔篩選特定的身分組白名單（若未設定則抓取全部）。
  4. 將抓取到的資料，自動導入並寫入到指定的 Google 試算表 (Google Sheets) 欄位中。
* **未來擴充目標**：未來計畫將資料儲存端從 Google 試算表替換為 Web 架構（如關聯式資料庫與網頁後台）。

## 🏗️ 系統架構與實體路徑 (Architecture & Directory)
* **專案實體路徑**：`f:\JACKFUN\DC`
* **資料夾結構**：
  ```text
  DC/
  ├── .venv/               # Python 虛擬環境資料夾 (不納入 Git 追蹤)
  ├── .vscode/             # VS Code 專案設定資料夾
  │   └── settings.json    # 自動設定本地 .venv 直譯器
  ├── .env                 # 存放 Discord Token (機密金鑰，不納入 Git)
  ├── requirements.txt     # 記錄相依套件 (discord.py, python-dotenv, gspread)
  ├── pyproject.toml       # Pyrefly & Pyright 靜態分析設定檔 (指定虛擬環境路徑)
  ├── server_config.json   # 儲存各伺服器的金鑰與身分組設定檔
  ├── main.py              # 程式進入點：負責啟動機器人
  ├── core_bot.py          # 核心互動邏輯：處理指令 (!setup_sheet, !setup_roles, !setup_show)、表情符號事件與寫入呼叫
  ├── storage_sheets.py    # 儲存模組：實作 gspread 動態金鑰寫入，並包含防禦性模擬模式
  └── project_context.md   # 本專案上下文文件 (提供給 AI 助手快速讀取)
  ```

## ⚙️ 環境變數設定 (.env)
* **DISCORD_TOKEN**：機器人登入 Token (已從 Discord Developer Portal 取得並設定)。

## ⏳ 目前進度 (Current Status)
1. **已完成**：
   * 在 `f:\JACKFUN\DC` 建立完整專案結構與環境。
   * 成功建置 Python 虛擬環境 (`.venv`) 並排除了 Git 追蹤。
   * 完成 `.vscode/settings.json` 與 `pyproject.toml` 設定，解決了 Pyrefly 所有型態警告與紅字問題。
   * 成功重構專案為「多伺服器獨立設定」架構：
     * 支援伺服器管理員以指令設定試算表與篩選身分組，並自動寫入 `server_config.json`。
     * 完成 `storage_sheets.py` 透過 `gspread` 動態打開指定試算表並寫入資料的邏輯。
     * `storage_sheets.py` 內建防禦性「模擬模式」，即使無憑證亦不閃退。
   * 機器人已在本地背景成功連線執行，連線正常。
2. **待進行**：
   * 申請 Google Cloud 專案並取得服務帳戶憑證 `creds.json` 放至專案目錄。
   * 建立您的 Google 試算表，將服務帳戶 Email 加入共用，並使用 `!setup_sheet` 進行伺服器設定與最終寫入驗證。

