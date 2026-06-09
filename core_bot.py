"""
核心互動模組 (core_bot.py)
專責 Discord 機器人的互動邏輯，包含監聽表情符號與基礎測試指令。
"""

import discord
from storage_sheets import StorageSheets

class DiscordBot(discord.Client):
    def __init__(self, storage_client: StorageSheets, target_roles: list[str]):
        """
        初始化 Discord 機器人。
        
        :param storage_client: 實作儲存功能的物件 (例如 StorageSheets 實例)
        :param target_roles: 需要篩選的特定身分組名稱清單
        """
        # 設定 Discord 機器人所需的權限 (Intents)
        intents = discord.Intents.default()
        
        # 啟用讀取訊息內容的權限 (用於 !ping 指令)
        intents.message_content = True
        
        # 啟用伺服器成員權限 (用於讀取使用者的身分組資訊)
        # 注意：這需要在 Discord Developer Portal 的 Bot 頁面中開啟 "Server Members Intent"
        intents.members = True
        
        # 呼叫父類別 (discord.Client) 的初始化方法
        super().__init__(intents=intents)
        
        # 將儲存模組的實例保存為成員變數，方便後續呼叫
        self.storage = storage_client

        # 保存特定身分組篩選清單
        self.target_roles = target_roles

    async def on_ready(self):
        """
        當機器人成功連線並準備就緒時觸發。
        """
        print(f"[Bot] 機器人已成功上線！")
        print(f"[Bot] 登入帳號：{self.user.name} (ID: {self.user.id})")
        print("--------------------------------------------------")

    async def on_message(self, message: discord.Message):
        """
        當伺服器中有新訊息發送時觸發。
        
        :param message: 訊息物件
        """
        # 防禦性設計：避免機器人回覆自己發送的訊息，造成無限迴圈
        if message.author == self.user:
            return

        # 簡單的連線測試指令
        if message.content.lower() == "!ping":
            try:
                await message.channel.send("🏓 pong! 機器人運作正常！")
                print(f"[Bot] 已回應 {message.author.name} 的 !ping 指令。")
            except discord.Forbidden:
                print(f"[Bot][錯誤] 無法在頻道發送訊息，請檢查機器人權限。")
            except Exception as e:
                print(f"[Bot][錯誤] 處理 !ping 時發生異常: {e}")

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """
        當有使用者對訊息點擊表情符號 (Reaction) 時觸發。
        使用 Raw 事件是為了確保機器人即使重啟，也能監聽歷史訊息的表情符號。
        
        :param payload: 表情符號事件的詳細資料
        """
        # 排除機器人自己點擊表情符號的狀況
        if payload.user_id == self.user.id:
            return

        print(f"[Bot] 偵測到表情符號互動！")
        print(f" - 使用者 ID: {payload.user_id}")
        print(f" - 點擊的表情符號: {payload.emoji}")

        # 嘗試獲取該使用者所在的伺服器 (Guild)
        guild = self.get_guild(payload.guild_id)
        if not guild:
            # 如果機器人沒在快取中找到伺服器，嘗試從 API 異步獲取
            try:
                guild = await self.fetch_guild(payload.guild_id)
            except Exception as e:
                print(f"[Bot][錯誤] 無法取得伺服器資訊: {e}")
                return

        # 獲取點擊表情符號的成員物件 (Member) 以讀取身分組
        member = payload.member
        if not member:
            # 在某些特定情況下 payload.member 可能為 None，我們需要主動獲取
            try:
                member = await guild.fetch_member(payload.user_id)
            except Exception as e:
                print(f"[Bot][錯誤] 無法取得成員 (ID: {payload.user_id}) 的詳細資訊: {e}")
                return

        # 提取使用者的身分組名稱清單
        # 如果有設定特定身分組白名單，就只篩選出白名單內的身分組；否則保留所有身分組 (排除 @everyone)
        if self.target_roles:
            roles = [role.name for role in member.roles if role.name in self.target_roles]
        else:
            roles = [role.name for role in member.roles if role.name != "@everyone"]
        
        print(f" - 使用者名稱: {member.name}")
        print(f" - 身分組清單: {roles}")

        # 呼叫儲存模組，將資料寫入試算表 (目前為模擬寫入)
        success = self.storage.write_user_data(
            user_id=member.id,
            username=member.name,
            roles=roles
        )
        
        if success:
            print(f"[Bot] 使用者資料已成功傳送至儲存模組。")
        else:
            print(f"[Bot][警告] 傳送使用者資料至儲存模組時失敗。")
        print("--------------------------------------------------")
