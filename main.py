import discord
from discord.ext import tasks
from discord import app_commands
import asyncio
import json
import os
from datetime import datetime
import pytz

TOKEN = os.getenv("TOKEN")  # 環境変数から取得
OWNER_ID = 1169403605162405891
ITEMS_FILE = "items.json"

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

data = {"items": {}, "achievement_channel_id": None}

def load_data():
    global data
    if os.path.exists(ITEMS_FILE):
        with open(ITEMS_FILE, "r") as f:
            data = json.load(f)
            if "items" not in data:
                data["items"] = {}
            if "achievement_channel_id" not in data:
                data["achievement_channel_id"] = None

def save_data():
    with open(ITEMS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

load_data()

def get_jst_now():
    jst = pytz.timezone("Asia/Tokyo")
    return datetime.now(jst)

@tasks.loop(minutes=10)
async def uptime_notify():
    user = await bot.fetch_user(OWNER_ID)
    now = get_jst_now()
    weekday = ["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"][now.weekday()]
    await user.send(f"✅ BOT稼働中￤{now.strftime('%Y-%m-%d')}（{weekday}）{now.strftime('%H:%M:%S')}")

async def send_achievement(user, item_name, guild_name):
    ch_id = data.get("achievement_channel_id")
    if ch_id:
        ch = bot.get_channel(ch_id)
        if ch:
            now = get_jst_now()
            weekday = ["月", "火", "水", "木", "金", "土", "日"][now.weekday()]
            embed = discord.Embed(title="📦 商品名", description=f"**{item_name}**")
            embed.add_field(name="🧾 購入数", value="1個", inline=True)
            embed.add_field(name="🙋‍♂️ 購入者", value=user.mention, inline=True)
            embed.add_field(name="🌐 購入サーバー", value=guild_name, inline=False)
            embed.set_footer(text=f"{now.strftime('%Y-%m-%d')}（{weekday}）{now.strftime('%H:%M:%S')}")
            await ch.send(embed=embed)

class PurchaseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for name in data["items"]:
            if isinstance(name, str) and name.strip() != "" and name.isprintable():
                self.add_item(PurchaseButton(name))

class PurchaseButton(discord.ui.Button):
    def __init__(self, item_name):
        super().__init__(label=item_name, style=discord.ButtonStyle.primary, custom_id=f"buy_{item_name}")
        self.item_name = item_name

    async def callback(self, interaction: discord.Interaction):
        item = data["items"].get(self.item_name)
        if not item:
            await interaction.response.send_message("商品が見つかりません。", ephemeral=True)
            return
        if item["stock"] != 0:
            if item["stock"] <= 0:
                await interaction.response.send_message("在庫切れです。", ephemeral=True)
                return
            item["stock"] -= 1
            save_data()
        try:
            await interaction.user.send(f"🎁 **{self.item_name}** の中身：\n{item['content']}")
        except:
            await interaction.response.send_message("DM送信に失敗しました。", ephemeral=True)
            return
        await interaction.response.send_message("✅ 購入が完了しました。DMを確認してください。", ephemeral=True)
        await send_achievement(interaction.user, self.item_name, interaction.guild.name)

@bot.event
async def on_ready():
    bot.add_view(PurchaseView())
    await tree.sync()
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Pan_Bot"))
    uptime_notify.start()
    print("Bot is ready.")

@tree.command(name="商品追加", description="商品を追加します")
@app_commands.describe(商品名="商品名", 中身="DMで送る内容", 在庫数="在庫数（0なら無限）")
async def add_item(interaction: discord.Interaction, 商品名: str, 中身: str, 在庫数: int):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("権限がありません。", ephemeral=True)
        return
    data["items"][商品名] = {"content": 中身, "stock": 在庫数}
    save_data()
    await interaction.response.send_message(f"{商品名} を追加しました。")

@tree.command(name="商品削除", description="商品を削除します")
@app_commands.describe(商品名="削除したい商品名")
async def delete_item(interaction: discord.Interaction, 商品名: str):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("権限がありません。", ephemeral=True)
        return
    if 商品名 in data["items"]:
        del data["items"][商品名]
        save_data()
        await interaction.response.send_message(f"{商品名} を削除しました。")
    else:
        await interaction.response.send_message("その商品は存在しません。", ephemeral=True)

@tree.command(name="パネル設置", description="自販機のパネルを設置")
@app_commands.describe(タイトル="パネルタイトル", 概要="説明文")
async def setup_panel(interaction: discord.Interaction, タイトル: str, 概要: str):
    embed = discord.Embed(title=タイトル, description=概要)
    await interaction.response.send_message(embed=embed, view=PurchaseView())

@tree.command(name="実績チャンネル設定", description="実績を送るチャンネルを設定")
@app_commands.describe(チャンネル="送信先チャンネル")
async def set_channel(interaction: discord.Interaction, チャンネル: discord.TextChannel):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("権限がありません。", ephemeral=True)
        return
    data["achievement_channel_id"] = チャンネル.id
    save_data()
    await interaction.response.send_message(f"実績チャンネルを {チャンネル.mention} に設定しました。")

bot.run(TOKEN)
