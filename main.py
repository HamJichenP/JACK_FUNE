"""
專案進入點 (main.py)
負責載入設定、初始化各個模組，並啟動 Discord 機器人。
"""

import os
import sys
import discord
from dotenv import load_dotenv
from core_bot import DiscordBot
from storage_sheets import StorageSheets

def main():
    print("==================================================")
    print("           MyDiscordBot 啟動程序開始              ")
    print("==================================================")

    # 1. 載入 .env 檔案中的環境變數
    # load_dotenv() 會自動尋找當前目錄底下的 .env 檔案，並將其變數載入到系統環境變數中
    load_dotenv()

    # 2. 讀取並驗證必要環境變數 (防禦性設計)
    discord_token = os.getenv("DISCORD_TOKEN")
    sheets_key = os.getenv("GOOGLE_SHEETS_KEY")

    # 檢查 Token 是否存在或是否仍為預設的 placeholder
    if not discord_token or discord_token == "your_discord_token_here":
        print("[系統錯誤] 找不到有效的 Discord Token！")
        print("請確認專案目錄下的 `.env` 檔案中是否已正確填入 `DISCORD_TOKEN`。")
        print("程式即將關閉。")
        sys.exit(1)

    if not sheets_key or sheets_key == "your_google_sheets_key_here":
        # 這是非致命錯誤，僅發出警告，暫不中止程式
        print("[系統警告] 找不到有效的 Google Sheets Key，寫入功能將僅以模擬模式運行。")
        sheets_key = "MOCK_KEY"

    # 3. 初始化儲存模組與機器人
    try:
        # 初始化儲存模組
        storage = StorageSheets(spreadsheet_key=sheets_key)
        
        # 讀取並處理特定身分組篩選清單 (以半形逗號分割)
        target_roles_str = os.getenv("TARGET_ROLES", "")
        target_roles = [r.strip() for r in target_roles_str.split(",") if r.strip()]
        if target_roles:
            print(f"[系統] 已設定特定身分組篩選白名單: {target_roles}")
        else:
            print("[系統] 未設定特定身分組，將抓取使用者擁有的所有身分組。")

        # 初始化機器人，將儲存模組與篩選清單傳遞進去
        bot = DiscordBot(storage_client=storage, target_roles=target_roles)
        
    except Exception as e:
        print(f"[系統錯誤] 模組初始化失敗: {e}")
        sys.exit(1)

    # 4. 啟動 Discord 機器人
    try:
        print("[系統] 正在嘗試連線至 Discord...")
        bot.run(discord_token)
    except discord.errors.LoginFailure:
        print("[系統錯誤] 登入失敗！請確認你的 `DISCORD_TOKEN` 是否正確。")
    except Exception as e:
        print(f"[系統錯誤] 機器人執行時發生異常: {e}")

if __name__ == "__main__":
    main()
