import os
import asyncio
import random
import discord
from discord.ext import commands
from discord import app_commands
from openai import AsyncOpenAI
import google.generativeai as genai
import asyncpg
from collections import defaultdict

# --- 環境変数から各種キーを取得 ---
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

DUO_CHANNEL_ID = int(os.getenv("DUO_CHANNEL_ID", "1010000000000000000"))
MBTI_HISTORY_CHANNELS = [int(x) for x in os.getenv("MBTI_HISTORY_CHANNELS", "1010000000000000010,1010000000000000020").split(",") if x.strip()]
MBTI_HISTORY_SCAN_LIMIT = int(os.getenv("MBTI_HISTORY_SCAN_LIMIT", "200"))

TARGET_CHANNEL_IDS = [1010000000000000030, 1010000000000000040]
CHECK_MARK = "✅"
ALLOWED_USER_IDS = [1011111111111111111, 1012222222222222222]

DM_SEND_INTERVAL = 0.2
AI_REPLY_INTERVAL = 0.3

vc_profile_messages = defaultdict(dict)

# --- AI API初期化 ---
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-pro-latest")
else:
    gemini_model = None

# --- MBTIタイプ定義（提出用の一部例のみ） ---
compatibility = {
    "Architect": ["Consul", "Debater", "Adventurer"],
    "Logician": ["Entertainer", "Commander", "Defender"],
}
role_ids = {
    "Architect": "1011010101010101001",
    "Logician": "1011010101010101002",
}

# --- Discord Bot基本設定 ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.guilds = True
intents.reactions = True

# --- VC入退室時にプロフィールEmbedを出す ---
async def get_profile_link(guild: discord.Guild, member: discord.Member):
    for cid in MBTI_HISTORY_CHANNELS:
        ch = guild.get_channel(cid)
        if isinstance(ch, discord.TextChannel):
            async for m in ch.history(limit=100):
                if m.author.id == member.id:
                    return f"https://discord.com/channels/{guild.id}/{ch.id}/{m.id}"
    return None

def create_profile_embed(url):
    return discord.Embed(
        title="相手のプロフィール",
        description=f"[プロフィールを見る]({url})" if url else "プロフィール未登録",
        color=0xFDB813
    )

# --- MBTIのロール＆履歴からタイプを拾って返す ---
class MBTICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_listener(self.on_voice_state_update, name='on_voice_state_update')

    async def on_voice_state_update(self, member, before, after):
        # 退出時はメッセージを消す
        if before.channel and (after.channel is None or before.channel.id != after.channel.id):
            msg_map = vc_profile_messages.get(before.channel.id, {})
            msg_id = msg_map.pop(member.id, None)
            if msg_id:
                text_ch = self.bot.get_partial_messageable(before.channel.id)
                try:
                    msg = await text_ch.fetch_message(msg_id)
                    await msg.delete()
                except Exception:
                    pass
            if not msg_map:
                vc_profile_messages.pop(before.channel.id, None)

        # 入室時はプロフィール表示
        if after.channel and (before.channel is None or before.channel.id != after.channel.id):
            if member.bot:
                return
            if after.channel.id == 1010000000000000100:
                return
            text_ch = self.bot.get_partial_messageable(after.channel.id)
            link = await get_profile_link(member.guild, member)
            desc = f"[プロフィールを見る]({link})" if link else "プロフィール未登録"
            embed = discord.Embed(description=desc, color=0xFFD1DC)
            embed.set_author(name=f"@{member.display_name}", icon_url=member.display_avatar.url)
            try:
                sent = await text_ch.send(embed=embed)
                vc_profile_messages[after.channel.id][member.id] = sent.id
            except Exception:
                pass

    async def get_user_mbti(self, guild, member):
        for role in member.roles:
            if str(role.id) in role_ids.values():
                for k, v in role_ids.items():
                    if v == str(role.id):
                        return k
        for ch_id in MBTI_HISTORY_CHANNELS:
            channel = guild.get_channel(ch_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                continue
            async for msg in channel.history(limit=MBTI_HISTORY_SCAN_LIMIT):
                if msg.author.id == member.id:
                    for role in member.roles:
                        if str(role.id) in role_ids.values():
                            for k, v in role_ids.items():
                                if v == str(role.id):
                                    return k
        return None

    async def run_compatibility(self, interaction, status_msg=None):
        if not status_msg:
            await interaction.followup.send("診断スタートします。少し待ってください。", ephemeral=True)
            status_msg = await interaction.original_response()

        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await status_msg.edit(content="サーバー内で実行してください。")
            return

        member = interaction.guild.get_member(interaction.user.id)
        await status_msg.edit(content="MBTIタイプ検索中…")
        user_mbti = await self.get_user_mbti(interaction.guild, member)
        if not user_mbti or user_mbti not in compatibility:
            await status_msg.edit(content="MBTIロールまたは履歴が見つかりませんでした。")
            return

        best_matches = compatibility[user_mbti]
        dm_channel = member.dm_channel or await member.create_dm()
        latest_messages_cache = {}
        if MBTI_HISTORY_CHANNELS:
            for hist_ch_id in MBTI_HISTORY_CHANNELS:
                channel_obj = interaction.guild.get_channel(hist_ch_id)
                if not channel_obj or not isinstance(channel_obj, discord.TextChannel): continue
                async for msg_hist in channel_obj.history(limit=MBTI_HISTORY_SCAN_LIMIT * 3):
                    if msg_hist.author.id not in latest_messages_cache and not msg_hist.author.bot:
                        latest_messages_cache[msg_hist.author.id] = msg_hist

        num_matches = len(best_matches)
        for idx, target_mbti_name in enumerate(reversed(best_matches)):
            rank = num_matches - idx
            await status_msg.edit(content=f"{rank}位 ({target_mbti_name}) 検索中…")
            user_jump_links = []
            target_role_id_str = role_ids.get(target_mbti_name)
            if target_role_id_str:
                target_role = interaction.guild.get_role(int(target_role_id_str))
                if target_role:
                    for mem_with_role in target_role.members:
                        if mem_with_role.id == interaction.user.id: continue
                        latest_msg = latest_messages_cache.get(mem_with_role.id)
                        if latest_msg:
                            user_jump_links.append(f"<@{mem_with_role.id}> ([Jump]({latest_msg.jump_url}))")

            await status_msg.edit(content=f"{rank}位 ({target_mbti_name}) の結果をDM送信中…")
            if user_jump_links:
                embed = discord.Embed(description=f"**{rank}位: {target_mbti_name}**\n" + ", ".join(user_jump_links), color=discord.Color.gold())
                await dm_channel.send(embed=embed)
                await asyncio.sleep(DM_SEND_INTERVAL)
            else:
                embed = discord.Embed(
                    title=f"{rank}位: {target_mbti_name}",
                    description="該当ユーザーが見つかりませんでした。",
                    color=discord.Color.light_grey()
                )
                await dm_channel.send(embed=embed)

        await status_msg.edit(content="診断完了！DMをチェックしてください。")
        await asyncio.sleep(10)
        try:
            await status_msg.delete()
        except Exception:
            pass

# --- 相性診断のView（ボタン） ---
class CompatibilityView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="相性診断", style=discord.ButtonStyle.primary, custom_id="compat_btn")
    async def compat_btn(self, interaction, button):
        await interaction.response.send_message("診断始めます。しばらくお待ちください。", ephemeral=True)
        status_msg = await interaction.original_response()
        await self.cog.run_compatibility(interaction, status_msg=status_msg)

# --- Bot & DB初期化 ---
class MyBot(commands.Bot):
    async def setup_hook(self):
        mbti_cog = MBTICog(self)
        await self.add_cog(mbti_cog)
        self.add_view(CompatibilityView(mbti_cog))

bot = MyBot(command_prefix="!", intents=intents)
pg_pool = None

async def init_db():
    global pg_pool
    if DATABASE_URL:
        pg_pool = await asyncpg.create_pool(DATABASE_URL)

# --- スラッシュコマンド登録 ---
@bot.tree.command(name="diagnosis", description="MBTI相性診断パネルを表示")
async def slash_diagnosis(interaction):
    embed = discord.Embed(
        title="MBTI Compatibility Panel",
        description="ボタンを押すと、あなたと相性の良いタイプがDMで届きます。",
        color=discord.Color.blue(),
    )
    view = CompatibilityView(bot.get_cog("MBTICog"))
    await interaction.channel.send(embed=embed, view=view)

# --- Bot起動 ---
@bot.event
async def on_ready():
    await init_db()
    try:
        synced = await bot.tree.sync()
        print(f"スラッシュコマンド同期数：{len(synced)}")
    except Exception as e:
        print(f"コマンド同期失敗: {e}")
    print(f"Bot ready: {bot.user}")

async def main():
    if not DISCORD_TOKEN:
        print("トークン未設定。終了します。")
        return
    async with bot:
        try:
            await bot.start(DISCORD_TOKEN)
        except discord.LoginFailure as e:
            print(f"ログイン失敗: {e}")
        except Exception as e:
            print(f"起動エラー: {e}")

if __name__ == "__main__":
    print("Bot起動")
    asyncio.run(main())
