"""
儲存模組 (storage_sheets.py)
專責 Google Sheets 的連線與寫入邏輯。
目前為 placeholder 實作，未來會正式與 Google Sheets API 進行串接。
"""

class StorageSheets:
    def __init__(self, spreadsheet_key: str):
        """
        初始化儲存模組。
        
        :param spreadsheet_key: Google 試算表的 Key (通常在網址中)
        """
        self.spreadsheet_key = spreadsheet_key
        print(f"[Storage] 儲存模組已初始化，使用試算表 Key: {self.spreadsheet_key}")

    def write_user_data(self, user_id: int, username: str, roles: list[str]) -> bool:
        """
        將使用者的 Discord ID 與身分組資訊寫入 Google 試算表。
        
        :param user_id: 使用者的 Discord ID (數字)
        :param username: 使用者的名稱 (字串)
        :param roles: 使用者目前擁有的身分組名稱清單
        :return: 寫入成功返回 True，失敗則返回 False
        """
        # 防禦性檢查：防範輸入為 None 或格式不正確
        if not user_id or not username:
            print("[Storage][錯誤] 寫入失敗，使用者 ID 或名稱不可為空。")
            return False
            
        # 暫時以主控台印出代替實際的試算表寫入
        print(f"[Storage][模擬寫入] 成功寫入資料 -> ID: {user_id}, 名稱: {username}, 身分組: {', '.join(roles)}")
        return True
