"""
核心互動模組 (core_bot.py)
專責 Discord 機器人的互動邏輯，包含多伺服器獨立設定（金鑰與篩選身分組）與寫入流程。
"""

import os
import json
import asyncio
import discord
from storage_sheets import StorageSheets

CONFIG_FILE = "server_config.json"
TEMPLATE_COPY_URL = "https://docs.google.com/spreadsheets/d/1hRvW70XsD4d3WBlaaHQ8JytAHNDWRKL8r54tdHca4Bk/copy"

class RoleSelect(discord.ui.Select):
    def __init__(self, bot: 'DiscordBot', day: str, gas_url: str, roles: list[str]):
        """
        自訂下拉選單元件，用於讓有多重武學身分組的成員選擇其一報名。
        """
        self.bot = bot
        self.day = day
        self.gas_url = gas_url

        # 建立選單選項 (最多 25 個，Discord API 限制)
        options = [
            discord.SelectOption(label=role_name, value=role_name, emoji="⚔️")
            for role_name in roles[:25]
        ]
        
        super().__init__(
            placeholder="請選擇您此戰要使用的武學身分...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        # 取得使用者所選取的單一身分組
        selected_role = self.values[0]
        member = interaction.user
        
        # 點選後立即將原下拉選單訊息更新為處理中狀態並清除選單元件，防止重複點擊並維持畫面清爽
        await interaction.response.edit_message(content="⏳ 正在處理報名資料，請稍候...", view=None)
        
        # 呼叫非同步寫入方法，將選定的單一身分組寫入試算表
        success = await self.bot.storage.write_user_data_via_gas(
            gas_url=self.gas_url,
            display_name=member.display_name if isinstance(member, discord.Member) else member.name,
            roles=[selected_role],
            registered_day=self.day
        )
        
        msg = None
        if success:
            # 發送公開的成功報名訊息，以利 2 秒後機器人能將其完全刪除以維持版面乾淨
            msg = await interaction.followup.send(
                f"✅ **報名成功！**\n"
                f"📅 報名日期：`{self.day}`\n"
                f"👤 登記名稱：`{member.display_name if isinstance(member, discord.Member) else member.name}`\n"
                f"🏷️ 選擇武學：`{selected_role}`",
                ephemeral=False
            )
        else:
            msg = await interaction.followup.send(
                "❌ **報名失敗！**\n"
                "無法連線或寫入 Google 試算表，請聯絡伺服器管理員確認 GAS 網址設定與權限是否正確。",
                ephemeral=False
            )
        
        # 嘗試清除最初的「處理中」隱密提示訊息
        try:
            await interaction.delete_original_response()
        except Exception:
            try:
                await interaction.edit_original_response(content="✅ 登記程序已完成。")
            except Exception:
                pass

        # 延遲 2 秒後刪除公開的通知訊息
        await asyncio.sleep(2.0)
        if msg:
            try:
                await msg.delete()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除公開的報名結果訊息: {e}")



class RoleSelectionView(discord.ui.View):
    def __init__(self, bot: 'DiscordBot', day: str, gas_url: str, roles: list[str]):
        """
        自訂的下拉選單視圖，這裡的 timeout 設為 60 秒以自動回收，不需使用持久化 (Persistent)。
        """
        super().__init__(timeout=60)
        self.add_item(RoleSelect(bot, day, gas_url, roles))


class RegistrationView(discord.ui.View):
    def __init__(self, bot: 'DiscordBot'):
        """
        初始化持久化報名按鈕視圖。
        設定 timeout=None 是持久化視圖的關鍵，這表示視圖不會因逾時而失效。
        """
        super().__init__(timeout=None)
        self.bot = bot

    async def handle_registration(self, interaction: discord.Interaction, day: str):
        """共通的報名處理邏輯"""
        guild = interaction.guild
        member = interaction.user

        # 防禦性檢查：確保是在伺服器中，且發起人為 Member 類型
        if guild is None or not isinstance(member, discord.Member):
            await interaction.response.send_message("❌ 此功能僅限於伺服器頻道中使用。", ephemeral=True)
            return

        guild_id = str(guild.id)
        config = self.bot.load_config()
        server_cfg = config.get(guild_id, {})

        gas_url = server_cfg.get("gas_web_app_url")
        if not gas_url:
            await interaction.response.send_message(
                "❌ 此伺服器尚未設定 Google GAS Web App 網址，無法進行報名。請聯絡管理員使用 `!setup_gas` 進行設定。",
                ephemeral=False
            )
            await asyncio.sleep(2.0)
            try:
                await interaction.delete_original_response()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除設定錯誤提示: {e}")
            return

        target_roles = server_cfg.get("target_roles", [])

        # 過濾身分組
        if target_roles:
            roles = [role.name for role in member.roles if role.name in target_roles]
        else:
            roles = [role.name for role in member.roles if role.name != "@everyone"]

        # 智慧過濾與選單分流邏輯
        if not roles:
            # 情況 3：沒有任何符合白名單的身分組 -> 直接回覆失敗 (使用公開訊息)
            await interaction.response.send_message(
                "❌ **報名失敗**\n"
                "您目前在伺服器中沒有擁有任何符合登記要求的武學身分組。\n"
                "*提示：請先向幹部申請對應的武學身分組。*",
                ephemeral=False
            )
            # 2 秒後自動刪除此回覆
            await asyncio.sleep(2.0)
            try:
                await interaction.delete_original_response()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除失敗提示訊息: {e}")
            return

        if len(roles) == 1:
            # 情況 1：只擁有一個符合身分組 -> 直接一鍵快速報名
            # 先延遲回應 (Defer) 為公開訊息，避免網路傳輸超時，以利 2 秒後刪除
            await interaction.response.defer(ephemeral=False)
            
            success = await self.bot.storage.write_user_data_via_gas(
                gas_url=gas_url,
                display_name=member.display_name,
                roles=roles,
                registered_day=day
            )
            
            if success:
                await interaction.edit_original_response(
                    content=f"✅ **報名成功！**\n"
                            f"📅 報名日期：`{day}`\n"
                            f"👤 登記名稱：`{member.display_name}`\n"
                            f"🏷️ 登記武學：`{roles[0]}`"
                )
            else:
                await interaction.edit_original_response(
                    content="❌ **報名失敗！**\n"
                            "無法連線或寫入 Google 試算表，請聯絡伺服器管理員確認：\n"
                            "1. Google GAS 網址設定是否正確\n"
                            "2. 該 GAS 網頁應用程式是否已部署，且存取權限設定為「任何人 (Anyone)」\n"
                            "3. 本機網路是否能正常連線至外部 API"
                )
            # 2 秒後自動刪除報名結果訊息
            await asyncio.sleep(2.0)
            try:
                await interaction.delete_original_response()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除報名結果訊息: {e}")
        else:
            # 情況 2：擁有多個符合身分組 -> 彈出下拉選單讓使用者自行挑選一個
            view = RoleSelectionView(self.bot, day, gas_url, roles)
            await interaction.response.send_message(
                "⚔️ **偵測到您擁有多個武學身分組**\n"
                "請於下方選單選擇您此戰要使用的武學進行登記：",
                view=view,
                ephemeral=True
            )

    # 星期六報名按鈕，設定唯一的 custom_id 是持久化視圖重啟後能繼續運作的關鍵
    @discord.ui.button(label="星期六 報名", style=discord.ButtonStyle.primary, custom_id="btn_register_saturday", emoji="💙")
    async def register_saturday(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_registration(interaction, "星期六")

    # 星期日報名按鈕
    @discord.ui.button(label="星期日 報名", style=discord.ButtonStyle.success, custom_id="btn_register_sunday", emoji="💚")
    async def register_sunday(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_registration(interaction, "星期日")


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
        if self.user:
            print(f"[Bot] 登入帳號：{self.user.name} (ID: {self.user.id})")
        
        # 註冊 Persistent View 讓舊按鈕在機器人重啟後依然有效
        self.add_view(RegistrationView(self))
        print("[Bot] 已成功註冊持久化按鈕視圖 (Persistent View)")
        print("--------------------------------------------------")

    async def on_message(self, message: discord.Message):
        """當伺服器中有新訊息發送時觸發 (處理設定指令與連線測試)"""
        # 排除機器人自己發送的訊息
        if message.author == self.user:
            return

        # 防禦性檢查：排除私訊 (DM) 且確保作者為伺服器成員 (Member)
        if message.guild is None or not isinstance(message.author, discord.Member):
            return

        # 1. 連線測試指令
        if message.content.lower() == "!ping":
            msg = await message.channel.send("🏓 pong! 機器人運作正常！")
            await msg.delete(delay=2.0)
            try:
                await message.delete()
            except Exception:
                pass
            return

        # 2. 設定試算表金鑰指令 (!setup_sheet <Key>)
        if message.content.startswith("!setup_sheet"):
            # 權限檢查：限制只有管理員能執行
            if not message.author.guild_permissions.administrator:
                msg = await message.channel.send("❌ 只有具備「管理員 (Administrator)」權限的成員才能使用此指令。")
                await msg.delete(delay=2.0)
                try:
                    await message.delete()
                except Exception:
                    pass
                return

            parts = message.content.split(maxsplit=1)
            if len(parts) < 2:
                msg = await message.channel.send("❌ 用法錯誤！請使用：`!setup_sheet <您的Google試算表Key>`")
                await msg.delete(delay=2.0)
                try:
                    await message.delete()
                except Exception:
                    pass
                return

            sheet_key = parts[1].strip()
            guild_id = str(message.guild.id)
            
            config = self.load_config()
            if guild_id not in config:
                config[guild_id] = {}
            config[guild_id]["google_sheets_key"] = sheet_key
            self.save_config(config)

            msg = await message.channel.send(f"✅ 已成功設定此伺服器的 Google 試算表金鑰！\n金鑰：`{sheet_key}`")
            # 2 秒後自動刪除機器人的提示訊息
            await msg.delete(delay=2.0)
            
            # 自動刪除管理員打的指令訊息
            try:
                await message.delete()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除指令訊息: {e}")
            print(f"[Bot][設定] 伺服器 {message.guild.name} (ID: {guild_id}) 已更新試算表金鑰。")
            return

        # 3. 設定篩選身分組指令 (!setup_roles <身分組1,身分組2,...>)
        if message.content.startswith("!setup_roles"):
            if not message.author.guild_permissions.administrator:
                msg = await message.channel.send("❌ 只有具備「管理員 (Administrator)」權限的成員才能使用此指令。")
                await msg.delete(delay=2.0)
                try:
                    await message.delete()
                except Exception:
                    pass
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
                msg = await message.channel.send("✅ 已清除身分組篩選限制，未來將記錄成員所擁有的所有身分組（排除 @everyone）。")
                await msg.delete(delay=2.0)
                print(f"[Bot][設定] 伺服器 {message.guild.name} (ID: {guild_id}) 已清除身分組篩選條件。")
            else:
                roles = [r.strip() for r in parts[1].split(",") if r.strip()]
                config[guild_id]["target_roles"] = roles
                self.save_config(config)
                msg = await message.channel.send(f"✅ 已成功設定此伺服器的篩選身分組白名單：`{', '.join(roles)}`")
                await msg.delete(delay=2.0)
                print(f"[Bot][設定] 伺服器 {message.guild.name} (ID: {guild_id}) 設定篩選身分組：{roles}")
            
            # 自動刪除管理員的設定指令
            try:
                await message.delete()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除指令訊息: {e}")
            return

        # 4. 顯示目前伺服器設定指令 (!setup_show)
        if message.content.lower() == "!setup_show":
            guild_id = str(message.guild.id)
            config = self.load_config()
            server_cfg = config.get(guild_id, {})
            
            sheet_key = server_cfg.get("google_sheets_key", "尚未設定")
            gas_url = server_cfg.get("gas_web_app_url", "尚未設定")
            target_roles = server_cfg.get("target_roles", [])
            roles_display = ", ".join(target_roles) if target_roles else "記錄所有身分組 (排除 @everyone)"
            
            embed = discord.Embed(
                title=f"📊 {message.guild.name} 機器人設定狀態",
                color=discord.Color.blue()
            )
            embed.add_field(name="Google GAS Web App 網址", value=f"`{gas_url}`", inline=False)
            embed.add_field(name="Google 試算表金鑰 (舊/備用)", value=f"`{sheet_key}`", inline=False)
            embed.add_field(name="篩選身分組白名單", value=roles_display, inline=False)
            embed.set_footer(text="提示：使用 !setup_gas 與 !setup_roles 進行修改")
            
            await message.channel.send(embed=embed)
            try:
                await message.delete()
            except Exception:
                pass
            return

        # 5. 部署報名按鈕指令 (!setup_buttons)
        if message.content.lower() == "!setup_buttons":
            if not message.author.guild_permissions.administrator:
                msg = await message.channel.send("❌ 只有具備「管理員 (Administrator)」權限的成員才能使用此指令。")
                await msg.delete(delay=2.0)
                try:
                    await message.delete()
                except Exception:
                    pass
                return

            embed = discord.Embed(
                title="📅 週末活動快速報名",
                description="請點擊下方按鈕選擇您想報名的日期。\n"
                            "系統會自動擷取您的**顯示名稱**與**身分組**寫入至 Google 試算表。\n\n"
                            "🔹 點選 **星期六 報名** 登記週六活動\n"
                            "🔸 點選 **星期日 報名** 登記週日活動\n\n"
                            "*備註：報名結果將以即時訊息回覆，並於 2 秒後由機器人完全刪除以維持頻道整潔。*",
                color=discord.Color.dark_teal()
            )
            view = RegistrationView(self)
            await message.channel.send(embed=embed, view=view)
            try:
                await message.delete()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除管理員設定指令訊息: {e}")
            return

        # 8. 設定 GAS Web App 網址指令 (!setup_gas <GAS網址>)
        if message.content.startswith("!setup_gas"):
            if not message.author.guild_permissions.administrator:
                msg = await message.channel.send("❌ 只有具備「管理員 (Administrator)」權限的成員才能使用此指令。")
                await msg.delete(delay=2.0)
                try:
                    await message.delete()
                except Exception:
                    pass
                return

            parts = message.content.split(maxsplit=1)
            guild_id = str(message.guild.id)
            config = self.load_config()
            if guild_id not in config:
                config[guild_id] = {}

            if len(parts) < 2 or parts[1].strip().lower() == "none":
                config[guild_id]["gas_web_app_url"] = ""
                self.save_config(config)
                msg = await message.channel.send("✅ 已清除此伺服器的 Google GAS 網址設定。")
                await msg.delete(delay=2.0)
                print(f"[Bot][設定] 伺服器 {message.guild.name} (ID: {guild_id}) 已清除 GAS 網址。")
            else:
                gas_url = parts[1].strip()
                if not (gas_url.startswith("http://") or gas_url.startswith("https://")):
                    msg = await message.channel.send("❌ 用法錯誤！請提供以 `http://` 或 `https://` 開頭的有效 GAS 網址。")
                    await msg.delete(delay=2.0)
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    return
                
                config[guild_id]["gas_web_app_url"] = gas_url
                self.save_config(config)
                msg = await message.channel.send(f"✅ 已成功設定此伺服器的 Google GAS Web App 網址！\n網址：`{gas_url}`")
                await msg.delete(delay=2.0)
                print(f"[Bot][設定] 伺服器 {message.guild.name} (ID: {guild_id}) 已設定 GAS 網址：{gas_url}")
            
            # 自動刪除管理員指令
            try:
                await message.delete()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除指令訊息: {e}")
            return

        # 9. 顯示架設與設定說明指令 (!setup_help)
        if message.content.lower() == "!setup_help":
            if not message.author.guild_permissions.administrator:
                msg = await message.channel.send("❌ 只有具備「管理員 (Administrator)」權限的成員才能使用此指令。")
                await msg.delete(delay=2.0)
                try:
                    await message.delete()
                except Exception:
                    pass
                return

            embed = discord.Embed(
                title="🛡️ 醉翁百業戰分隊表 - 架設與設定指南",
                description="請按照以下 4 個步驟，為您的伺服器架設專屬的百業戰報名系統：",
                color=discord.Color.brand_green()
            )
            embed.add_field(
                name="1️⃣ 一鍵複製試算表模板 (Google 官方範本)",
                value=f"請點擊下方連結，在您的雲端硬碟建立分隊表複本：\n"
                      f"👉 **[點此一鍵複製百業戰分隊表模板]({TEMPLATE_COPY_URL})**",
                inline=False
            )
            embed.add_field(
                name="2️⃣ 貼入並部署 Apps Script 腳本",
                value="1. 在複製好的試算表上方選單，點選 **「擴充功能」** -> **「Apps Script」**。\n"
                      "2. 複製專案中的 `gas_script.js` 全部程式碼，覆蓋貼上並儲存。\n"
                      "3. 點選右上角 **「部署」** -> **「新增部署」**。\n"
                      "4. 類型選擇 **「網頁應用程式 (Web App)」**：\n"
                      "   - *執行身分*：選擇您的帳戶。\n"
                      "   - *誰可以存取*：選擇 **「任何人 (Everyone)」** *(非常重要！)*。\n"
                      "5. 點選部署並授權，複製產生的 **「網頁應用程式網址」**。",
                inline=False
            )
            embed.add_field(
                name="3️⃣ 與 Discord 機器人進行綁定",
                value="在您伺服器的任何頻道中，輸入管理員指令綁定剛剛複製的網址：\n"
                      "```text\n!setup_gas <您複製的網頁應用程式網址>\n```\n"
                      "*(提示：您也可以使用 `!setup_roles 丐幫,霸刀` 設定要篩選的武學身分組。)*",
                inline=False
            )
            embed.add_field(
                name="4️⃣ 部署報名按鈕",
                value="在要提供成員報名的頻道中，輸入以下指令：\n"
                      "```text\n!setup_buttons\n```\n"
                      "機器人會發送「星期六/日」報名按鈕，成員即可開始登記！",
                inline=False
            )
            embed.set_footer(text="💡 您可以隨時輸入 !setup_show 檢視當前的設定狀態。")

            await message.channel.send(embed=embed)
            try:
                await message.delete()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除管理員說明指令訊息: {e}")
            return

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """當使用者對任何訊息點擊表情符號時觸發"""
        if self.user is None or payload.user_id == self.user.id:
            return

        # 防禦性檢查：排除沒有伺服器 ID 的私訊 (DM) 反應
        if not payload.guild_id:
            return

        # 1. 取得對應伺服器設定
        guild_id = str(payload.guild_id)
        config = self.load_config()
        server_cfg = config.get(guild_id, {})

        gas_url = server_cfg.get("gas_web_app_url")
        sheet_key = server_cfg.get("google_sheets_key")
        
        if not gas_url and not sheet_key:
            # 兩者皆未設定，無法寫入
            print(f"[Bot][忽略] 偵測到表情符號互動，但伺服器 (ID: {guild_id}) 尚未設定 GAS 網址或試算表金鑰！")
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
        print(f" - 名字: {member.display_name}")
        print(f" - 身分組: {roles}")

        # 4. 優先使用 GAS 非同步寫入，若未設定則回退至原生試算表寫入
        if gas_url:
            await self.storage.write_user_data_via_gas(
                gas_url=gas_url,
                display_name=member.display_name,
                roles=roles,
                registered_day="反應報名"
            )
        elif sheet_key:
            self.storage.write_user_data(
                spreadsheet_key=sheet_key,
                display_name=member.display_name,
                roles=roles,
                registered_day="反應報名"
            )
