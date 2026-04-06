import json
import discord
from discord.ext import commands
from discord import ui
from dotenv import load_dotenv
import os

# =========================
# CONFIGURAÇÃO DE AMBIENTE
# =========================
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(script_dir, ".env"))

ADMIN_CHANNEL_ID = 1487729614976712704  # Seu canal de ADM
BOT_TOKEN = os.getenv("TOKEN")

# =========================
# INTENTS
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# DATA HELPERS (JSON)
# =========================
def load_data():
    try:
        with open("coins.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_data(data):
    with open("coins.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

async def send_dm_receipt(user, title, description, fields=None, color=discord.Color.green()):
    """Envia um recibo ou notificação por DM para o jogador"""
    try:
        embed = discord.Embed(title=title, description=description, color=color)
        if fields:
            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)
        embed.set_footer(text="CZP • Sistema de Moedas")
        await user.send(embed=embed)
    except:
        pass

# =========================
# SHOP ITEMS (LISTA ORIGINAL COMPLETA)
# =========================
SHOP_ITEMS = {
    # ===== BASE =====
    1: {"name": "Caixa de Pregos", "price": 250, "desc": "Caixa de pregos para construção", "category": "🏗️ Base"},
    2: {"name": "Pacote de Tábuas (10)", "price": 300, "desc": "Pacote de tábuas para construção", "category": "🏗️ Base"},
    3: {"name": "Machadinha", "price": 100, "desc": "Ferramenta básica para construção", "category": "🏗️ Base"},
    4: {"name": "Martelo", "price": 100, "desc": "Ferramenta para construção", "category": "🏗️ Base"},
    5: {"name": "Pá", "price": 100, "desc": "Usada para enterrar itens", "category": "🏗️ Base"},
    6: {"name": "Serrote", "price": 200, "desc": "Usada para cortar planks", "category": "🏗️ Base"},
    7: {"name": "1un. Cimento, construção T3", "price": 380, "desc": "Fortalecer Base", "category": "🏗️ Base"},
    8: {"name": "Kit bandeira + bandeira", "price": 300, "desc": "Estabelecer Base", "category": "🚩 Base"},
    9: {"name": "Armario Militar Grande", "price": 300, "desc": "Armazenamento", "category": "🏗️ Base"},
    10: {"name": "Pedra de Amolar", "price": 150, "desc": "Pedra para afiar ferramentas e lâminas", "category": "Base"},
    # ===== VEÍCULOS =====
    11: {"name": "BMW", "price": 2500, "desc": "Veículo premium", "category": "🚗 Veículos"},
    12: {"name": "Ford F350", "price": 1500, "desc": "Caminhonete robusta", "category": "🚗 Veículos"},
    13: {"name": "Roda", "price": 300, "desc": "Roda para veículos", "category": "🚗 Veículos"},
    14: {"name": "Vela de Ignição", "price": 100, "desc": "Peça essencial para o motor", "category": "🚗 Veículos"},
    15: {"name": "Radiador", "price": 150, "desc": "Sistema de resfriamento", "category": "🚗 Veículos"},
    16: {"name": "Bateria de Carro", "price": 120, "desc": "Bateria para veículos", "category": "🚗 Veículos"},
    17: {"name": "Galão de Combustível", "price": 200, "desc": "Galão com combustível", "category": "🚗 Veículos"},
    18: {"name": "Chave de carro", "price": 350, "desc": "Trancar carro", "category": "🚗 Veículos"},

    # ===== SOBREVIVÊNCIA =====
    19: {"name": "Pacote de Comida", "price": 40, "desc": "Comida básica para sobrevivência", "category": "🎒 Sobrevivência"},
    20: {"name": "Garrafa de Água", "price": 25, "desc": "Água para viagem", "category": "🎒 Sobrevivência"},
    21: {"name": "Kit Médico", "price": 100, "desc": "Itens médicos básicos", "category": "🎒 Sobrevivência"},
    22: {"name": "Faca", "price": 20, "desc": "Ferramenta básica de sobrevivência", "category": "🎒 Sobrevivência"},

    # ===== PACOTES MMG =====
    23: {"name": "Pacote MMG Iniciante", "price": 350, "desc": "Kit MMG básico + mochila simples", "category": "🪖 Pacotes MMG"},
    24: {"name": "Pacote MMG Veterano", "price": 650, "desc": "Kit MMG completo + mochila média + colete", "category": "🪖 Pacotes MMG"},
    25: {"name": "Pacote MMG Elite", "price": 1500, "desc": "Kit MMG completo + mochila 120 slots", "category": "🪖 Pacotes MMG"},
}

# =========================
# UI: MODAL E VIEW
# =========================
class BuyModal(ui.Modal, title="Finalizar Compra CZP"):
    # NOVA FUNÇÃO: Campo para o Nick no Jogo
    ingame_nick = ui.TextInput(label="Seu Nick no Jogo", placeholder="Nick do personagem no DayZ", min_length=2, max_length=32)
    item_id = ui.TextInput(label="ID do Item", placeholder="Ex: 10", min_length=1, max_length=3)
    quantity = ui.TextInput(label="Quantidade", placeholder="Ex: 1", default="1", min_length=1, max_length=2)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            idx, qty = int(self.item_id.value), int(self.quantity.value)
            nick = self.ingame_nick.value
        except:
            return await interaction.followup.send("❌ Use apenas números nos campos!", ephemeral=True)

        if idx not in SHOP_ITEMS or qty <= 0:
            return await interaction.followup.send("❌ ID ou quantidade inválida.", ephemeral=True)

        item = SHOP_ITEMS[idx]
        total = item["price"] * qty
        data = load_data()
        uid = str(interaction.user.id)
        current_bal = data.get(uid, 0)

        if current_bal < total:
            return await interaction.followup.send(f"❌ Saldo insuficiente! Você tem {current_bal}💰 e precisa de {total}💰.", ephemeral=True)

        data[uid] = current_bal - total
        save_data(data)

        # Log no Canal de ADM (Incluindo o Nick)
        chan = bot.get_channel(ADMIN_CHANNEL_ID)
        if chan:
            log_embed = discord.Embed(title="🛒 Nova Compra", color=discord.Color.green())
            log_embed.add_field(name="Nick no Jogo", value=f"**{nick}**", inline=False)
            log_embed.add_field(name="Jogador", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Item", value=f"{qty}x {item['name']}", inline=True)
            log_embed.add_field(name="Custo", value=f"{total} moedas", inline=True)
            log_embed.add_field(name="Saldo Restante", value=f"{data[uid]} moedas", inline=True)
            await chan.send(embed=log_embed)

        await interaction.followup.send(f"✅ Compra realizada com sucesso! Nick informado: **{nick}**", ephemeral=True)
        await send_dm_receipt(interaction.user, "🧾 Recibo de Compra CZP", f"Você adquiriu {qty}x {item['name']} para o nick **{nick}**.", [("Total Pago", f"{total} moedas", True), ("Saldo Atual", f"{data[uid]} moedas", True)])

class PersistentShopView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🛒 Comprar Item", style=discord.ButtonStyle.success, custom_id="shop:buy_v_final")
    async def buy_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(BuyModal())

    @ui.button(label="💰 Ver Meu Saldo", style=discord.ButtonStyle.primary, custom_id="shop:bal_v_final")
    async def balance_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=False)
        bal = load_data().get(str(interaction.user.id), 0)
        try:
            await interaction.user.send(f"💰 Olá {interaction.user.name}! Seu saldo atual no CZP é: **{bal} moedas**.")
        except:
            pass

# =========================
# COMANDOS E EVENTOS
# =========================
@bot.event
async def on_ready():
    bot.add_view(PersistentShopView())
    print(f"✅ Bot Online como {bot.user}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_shop(ctx):
    await ctx.message.delete()
    embed = discord.Embed(title="🏪 MERCADO CZP - LISTA DE ITENS", description="Identifique o **ID** do item e clique no botão abaixo para comprar.", color=discord.Color.gold())
    cats = {}
    for iid, i in SHOP_ITEMS.items():
        cats.setdefault(i['category'], []).append(f"**ID: {iid}** • {i['name']} — **{i['price']}💰**\n> *{i['desc']}*")
    for cat, items in cats.items():
        content = "\n\n".join(items)
        embed.add_field(name=f"━━━ {cat} ━━━", value=content, inline=False)
    embed.set_footer(text="CZP Store • Use o botão abaixo para interagir")
    await ctx.send(embed=embed, view=PersistentShopView())

@bot.command()
@commands.has_permissions(administrator=True)
async def addcoins(ctx, member: discord.Member, amount: int):
    data = load_data()
    uid = str(member.id)
    data[uid] = data.get(uid, 0) + amount
    save_data(data)
    await ctx.send(f"✅ Adicionado {amount} moedas para {member.mention}.")
    await send_dm_receipt(member, "💰 Moedas Adicionadas", f"Um administrador adicionou **{amount} moedas** à sua conta.", [("Novo Saldo", f"{data[uid]}", False)], discord.Color.gold())

@bot.command()
@commands.has_permissions(administrator=True)
async def removecoins(ctx, member: discord.Member, amount: int):
    data = load_data()
    uid = str(member.id)
    data[uid] = max(0, data.get(uid, 0) - amount)
    save_data(data)
    await ctx.send(f"🗑️ Removido {amount} moedas de {member.mention}.")
    await send_dm_receipt(member, "⚠️ Moedas Removidas", f"Foram removidas **{amount} moedas** da sua conta.", [("Saldo Atual", f"{data[uid]}", False)], discord.Color.red())

@bot.command()
@commands.has_permissions(administrator=True)
async def reward(ctx, member: discord.Member, amount: int, *, reason="Vitória"):
    data = load_data()
    uid = str(member.id)
    data[uid] = data.get(uid, 0) + amount
    save_data(data)
    await ctx.send(f"🏆 {member.mention} ganhou {amount} por: {reason}")
    await send_dm_receipt(member, "🏆 Recompensa de Evento", f"Você ganhou **{amount} moedas**!\nMotivo: {reason}", color=discord.Color.purple())

@bot.command()
@commands.has_permissions(administrator=True)
async def giveall(ctx, amount: int):
    data = load_data()
    for m in ctx.guild.members:
        if not m.bot: data[str(m.id)] = data.get(str(m.id), 0) + amount
    save_data(data)
    await ctx.send(f"🌍 Distribuição global: Todos receberam {amount} moedas.")

@bot.command()
@commands.has_permissions(administrator=True)
async def takeall(ctx, amount: int):
    data = load_data()
    for m in ctx.guild.members:
        if not m.bot: data[str(m.id)] = max(0, data.get(str(m.id), 0) - amount)
    save_data(data)
    await ctx.send(f"🚨 Correção global: Removido {amount} moedas de todos.")

@bot.command()
@commands.has_permissions(administrator=True)
async def balance(ctx, member: discord.Member):
    bal = load_data().get(str(member.id), 0)
    await ctx.send(f"📊 O saldo de {member.mention} é **{bal} moedas**.")

bot.run(BOT_TOKEN)