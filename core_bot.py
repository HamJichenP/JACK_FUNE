"""
核心互動模組 (core_bot.py)
專責 Discord 機器人的互動邏輯，包含多伺服器獨立設定（金鑰與篩選身分組）與寫入流程。
"""

import os
import json
import discord
from storage_sheets import StorageSheets

CONFIG_FILE = "server_config.json"

class DiscordBot(discord.Client):
    def __init__(self, storage_client: StorageSheets):
        """
        初始化 Discord 機器人。
        
        :param storage_client: 儲存模組 (StorageSheets 實例)
        """
        # 設定 Discord 機器人所需的權限 (Intents)
        intents = discord.Intents.default()
        intents.message_content = True  # 用於讀取設定與測試指令
        intents.members = True          # 用於讀取成員身分組資訊
        
        super().__init__(intents=intents)
        self.storage = storage_client

    # --- 設定檔讀寫輔助方法 ---
    def load_config(self) -> dict:
        """載入伺服器設定檔"""
        if not os.path.exists(CONFIG_FILE):
            return {}
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Bot][設定錯誤] 無法讀取設定檔 {CONFIG_FILE}: {e}")
            return {}

    def save_config(self, config: dict):
        """儲存伺服器設定檔"""
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Bot][設定錯誤] 無法寫入設定檔 {CONFIG_FILE}: {e}")

    # --- Discord 事件監聽 ---
    async def on_ready(self):
        """當機器人成功登入並準備就緒時觸發"""
        print(f"[Bot] 機器人已成功上線！")
        print(f"[Bot] 登入帳號：{self.user.name} (ID: {self.user.id})")
        print("--------------------------------------------------")

    async def on_message(self, message: discord.Message):
        """當伺服器中有新訊息發送時觸發 (處理設定指令與連線測試)"""
        # 排除機器人自己發送的訊息
        if message.author == self.user:
            return

        # 1. 連線測試指令
        if message.content.lower() == "!ping":
            await message.channel.send("🏓 pong! 機器人運作正常！")
            return

        # 2. 設定試算表金鑰指令 (!setup_sheet <Key>)
        if message.content.startswith("!setup_sheet"):
            # 權限檢查：限制只有管理員能執行
            if not message.author.guild_permissions.administrator:
                await message.channel.send("❌ 只有具備「管理員 (Administrator)」權限的成員才能使用此指令。")
                return

            parts = message.content.split(maxsplit=1)
            if len(parts) < 2:
                await message.channel.send("❌ 用法錯誤！請使用：`!setup_sheet <您的Google試算表Key>`")
                return

            sheet_key = parts[1].strip()
            guild_id = str(message.guild.id)
            
            config = self.load_config()
            if guild_id not in config:
                config[guild_id] = {}
            config[guild_id]["google_sheets_key"] = sheet_key
            self.save_config(config)

            await message.channel.send(f"✅ 已成功設定此伺服器的 Google 試算表金鑰！\n金鑰：`{sheet_key}`")
            print(f"[Bot][設定] 伺服器 {message.guild.name} (ID: {guild_id}) 已更新試算表金鑰。")
            return

        # 3. 設定篩選身分組指令 (!setup_roles <身分組1,身分組2,...>)
        if message.content.startswith("!setup_roles"):
            if not message.author.guild_permissions.administrator:
                await message.channel.send("❌ 只有具備「管理員 (Administrator)」權限的成員才能使用此指令。")
                return

            parts = message.content.split(maxsplit=1)
            guild_id = str(message.guild.id)
            config = self.load_config()
            if guild_id not in config:
                config[guild_id] = {}

            if len(parts) < 2 or parts[1].strip().lower() == "none":
                # 清除篩選身分組，代表擷取全部
                config[guild_id]["target_roles"] = []
                self.save_config(config)
                await message.channel.send("✅ 已清除身分組篩選限制，未來將記錄成員所擁有的所有身分組（排除 @everyone）。")
                print(f"[Bot][設定] 伺服器 {message.guild.name} (ID: {guild_id}) 已清除身分組篩選條件。")
            else:
                roles = [r.strip() for r in parts[1].split(",") if r.strip()]
                config[guild_id]["target_roles"] = roles
                self.save_config(config)
                await message.channel.send(f"✅ 已成功設定此伺服器的篩選身分組白名單：`{', '.join(roles)}`")
                print(f"[Bot][設定] 伺服器 {message.guild.name} (ID: {guild_id}) 設定篩選身分組：{roles}")
            return

        # 4. 顯示目前伺服器設定指令 (!setup_show)
        if message.content.lower() == "!setup_show":
            guild_id = str(message.guild.id)
            config = self.load_config()
            server_cfg = config.get(guild_id, {})
            
            sheet_key = server_cfg.get("google_sheets_key", "尚未設定")
            target_roles = server_cfg.get("target_roles", [])
            roles_display = ", ".join(target_roles) if target_roles else "記錄所有身分組 (排除 @everyone)"
            
            embed = discord.Embed(
                title=f"📊 {message.guild.name} 機器人設定狀態",
                color=discord.Color.blue()
            )
            embed.add_field(name="Google 試算表金鑰", value=f"`{sheet_key}`", inline=False)
            embed.add_field(name="篩選身分組白名單", value=roles_display, inline=False)
            embed.set_footer(text="提示：使用 !setup_sheet 與 !setup_roles 進行修改")
            
            await message.channel.send(embed=embed)
            return

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """當使用者對任何訊息點擊表情符號時觸發"""
        if payload.user_id == self.user.id:
            return

        # 1. 取得對應伺服器設定
        guild_id = str(payload.guild_id)
        config = self.load_config()
        server_cfg = config.get(guild_id, {})

        sheet_key = server_cfg.get("google_sheets_key")
        if not sheet_key:
            # 該伺服器尚未設定試算表金鑰，不執行寫入動作
            print(f"[Bot][忽略] 偵測到表情符號互動，但伺服器 (ID: {guild_id}) 尚未設定 Google 試算表金鑰！")
            return

        target_roles = server_cfg.get("target_roles", [])

        # 2. 獲取點擊成員的詳細資料與身分組
        guild = self.get_guild(payload.guild_id)
        if not guild:
            try:
                guild = await self.fetch_guild(payload.guild_id)
            except Exception as e:
                print(f"[Bot][錯誤] 無法取得伺服器資訊: {e}")
                return

        member = payload.member
        if not member:
            try:
                member = await guild.fetch_member(payload.user_id)
            except Exception as e:
                print(f"[Bot][錯誤] 無法取得成員 (ID: {payload.user_id}) 資訊: {e}")
                return

        # 3. 過濾身分組
        if target_roles:
            roles = [role.name for role in member.roles if role.name in target_roles]
        else:
            roles = [role.name for role in member.roles if role.name != "@everyone"]

        print(f"[Bot] 伺服器 {guild.name} 偵測到表情符號互動：")
        print(f" - 使用者: {member.name} (ID: {member.id})")
        print(f" - 身分組: {roles}")

        # 4. 呼叫儲存模組寫入資料 (動態帶入此伺服器的 sheet_key)
        self.storage.write_user_data(
            spreadsheet_key=sheet_key,
            user_id=member.id,
            username=member.name,
            roles=roles
        )
