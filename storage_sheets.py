"""
儲存模組 (storage_sheets.py)
專責 Google Sheets API 的連線與寫入邏輯。
支援防禦性模擬模式：若 creds.json 不存在，會以模擬模式運行，避免程式崩潰。
"""

import os
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

class StorageSheets:
    def __init__(self, creds_path: str = "creds.json"):
        """
        初始化儲存模組，載入 Google 憑證。
        
        :param creds_path: 服務帳戶憑證 JSON 檔案的路徑
        """
        self.creds_path = creds_path
        self.gc = None
        self.mock_mode = False

        # 檢查憑證檔案是否存在
        if not os.path.exists(creds_path):
            print(f"[Storage][警告] 找不到憑證檔案 '{creds_path}'！")
            print("[Storage][提示] 將自動啟用【模擬模式】，所有寫入操作只會輸出至終端機。")
            self.mock_mode = True
            return

        try:
            # 設定 API 權限範圍 (Scope)
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            # 載入憑證並授權與 Google API 連線
            credentials = Credentials.from_service_account_file(creds_path, scopes=scopes)
            self.gc = gspread.authorize(credentials)
            print("[Storage] 儲存模組初始化完成，已成功連接 Google Sheets 用戶端。")
        except Exception as e:
            print(f"[Storage][錯誤] 憑證授權失敗: {e}")
            print("[Storage][提示] 連線失敗，切換為【模擬模式】。")
            self.mock_mode = True

    def write_user_data(self, spreadsheet_key: str, user_id: int, username: str, roles: list[str]) -> bool:
        """
        將使用者的 Discord ID 與身分組資訊寫入指定的 Google 試算表。
        
        :param spreadsheet_key: 該伺服器所設定的 Google 試算表 Key
        :param user_id: 使用者的 Discord ID (數字)
        :param username: 使用者的名稱 (字串)
        :param roles: 使用者目前擁有的身分組名稱清單
        :return: 寫入成功返回 True，失敗則返回 False
        """
        # 防禦性檢查：防範輸入為 None 或格式不正確
        if not user_id or not username:
            print("[Storage][錯誤] 寫入失敗，使用者 ID 或名稱不可為空。")
            return False

        # 取得當前台北時間（格式：yyyy-MM-dd HH:mm:ss）
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        roles_str = ", ".join(roles) if roles else "無身分組"

        # 模擬模式或試算表金鑰無效時，使用模擬寫入
        if self.mock_mode or not spreadsheet_key or spreadsheet_key == "MOCK_KEY":
            print(f"[Storage][模擬寫入] 成功寫入資料 (試算表 Key: {spreadsheet_key}) -> "
                  f"時間: {timestamp}, ID: {user_id}, 名稱: {username}, 身分組: {roles_str}")
            return True

        # 正式連線寫入
        try:
            # 1. 開啟試算表
            spreadsheet = self.gc.open_by_key(spreadsheet_key)
            
            # 2. 取得第一個分頁 (Worksheet)
            worksheet = spreadsheet.get_worksheet(0)
            
            # 3. 準備寫入的一列資料
            row_data = [timestamp, str(user_id), username, roles_str]
            
            # 4. 新增一列到最後面
            worksheet.append_row(row_data)
            
            print(f"[Storage] 已成功將資料寫入試算表 (Key: {spreadsheet_key})")
            return True
            
        except gspread.exceptions.APIError as e:
            print(f"[Storage][錯誤] Google API 呼叫錯誤: {e}")
            return False
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"[Storage][錯誤] 找不到指定的試算表，請檢查 Key: {spreadsheet_key}")
            return False
        except Exception as e:
            print(f"[Storage][錯誤] 寫入 Google Sheets 時發生未知異常: {e}")
            return False
