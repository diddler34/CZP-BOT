import json
import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

load_dotenv()

# =========================
# CONFIG
# =========================

ADMIN_CHANNEL_ID = 1487729614976712704  # your admin log channel ID
BOT_TOKEN = os.getenv("TOKEN")
print("BOT_TOKEN =", BOT_TOKEN)
PUBLIC_DELETE_DELAY = 8  # seconds before public bot replies disappear

# =========================
# INTENTS
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# DATA HELPERS
# =========================
def load_data():
    try:
        with open("coins.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def save_data(data):
    with open("coins.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def get_user_balance(user_id):
    data = load_data()
    return data.get(str(user_id), 0)


def add_user_coins(user_id, amount):
    data = load_data()
    user_id = str(user_id)
    data[user_id] = data.get(user_id, 0) + amount
    save_data(data)


def remove_user_coins(user_id, amount):
    data = load_data()
    user_id = str(user_id)
    current = data.get(user_id, 0)

    if current < amount:
        return False

    data[user_id] = current - amount
    save_data(data)
    return True


async def delete_command_message(ctx):
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        print(f"Sem permissão para apagar mensagens em #{ctx.channel}")
    except discord.HTTPException as e:
        print(f"Erro ao apagar mensagem em #{ctx.channel}: {e}")


async def send_dm_receipt(user, title, description, fields=None, color=discord.Color.green()):
    try:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )

        if fields:
            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)

        embed.set_footer(text="CZP • Recibo")
        await user.send(embed=embed)
        return True
    except discord.Forbidden:
        print(f"Não consegui enviar DM para {user}.")
        return False
    except discord.HTTPException as e:
        print(f"Erro ao enviar DM para {user}: {e}")
        return False


# =========================
# SHOP ITEMS
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
    
    # ===== VEÍCULOS =====
    6: {"name": "BMW", "price": 2500, "desc": "Veículo premium", "category": "🚗 Veículos"},
    7: {"name": "Ford F350", "price": 1500, "desc": "Caminhonete robusta", "category": "🚗 Veículos"},
    8: {"name": "Roda", "price": 300, "desc": "Roda para veículos", "category": "🚗 Veículos"},
    9: {"name": "Vela de Ignição", "price": 100, "desc": "Peça essencial para o motor", "category": "🚗 Veículos"},
    10: {"name": "Radiador", "price": 150, "desc": "Sistema de resfriamento", "category": "🚗 Veículos"},
    11: {"name": "Bateria de Carro", "price": 120, "desc": "Bateria para veículos", "category": "🚗 Veículos"},
    12: {"name": "Galão de Combustível", "price": 200, "desc": "Galão com combustível", "category": "🚗 Veículos"},
    12: {"name": "Chave de carro", "price": 350, "desc": "trancar carro", "category": "🚗 Veículos"},

    # ===== SOBREVIVÊNCIA =====
    13: {"name": "Pacote de Comida", "price": 40, "desc": "Comida básica para sobrevivência", "category": "🎒 Sobrevivência"},
    14: {"name": "Garrafa de Água", "price": 25, "desc": "Água para viagem", "category": "🎒 Sobrevivência"},
    15: {"name": "Kit Médico", "price": 100, "desc": "Itens médicos básicos", "category": "🎒 Sobrevivência"},
    16: {"name": "Faca", "price": 20, "desc": "Ferramenta básica de sobrevivência", "category": "🎒 Sobrevivência"},

    # ===== PACOTES MMG =====
    20: {
        "name": "Pacote MMG Iniciante",
        "price": 350,
        "desc": "Kit MMG básico + mochila simples pra começar bem",
        "category": "🪖 Pacotes MMG"
    },
    21: {
        "name": "Pacote MMG Veterano",
        "price": 650,
        "desc": "Kit MMG completo + mochila média + colete",
        "category": "🪖 Pacotes MMG"
    },
    22: {
        "name": "Pacote MMG Elite",
        "price": 1500,
        "desc": "Kit MMG completo + mochila 120 slots + equipamentos avançados",
        "category": "🪖 Pacotes MMG"
    },
}

# =========================
# EVENTS
# =========================
@bot.event
async def on_ready():
    print(f"Bot ligado como {bot.user}")
    print("Sistema de moedas online.")


# =========================
# COMMANDS
# =========================
@bot.command()
async def ping(ctx):
    await delete_command_message(ctx)
    await ctx.send("pong", delete_after=PUBLIC_DELETE_DELAY)


@bot.command()
async def coins(ctx):
    await delete_command_message(ctx)

    balance = get_user_balance(ctx.author.id)

    embed = discord.Embed(
        title="💰 Seu Saldo",
        description=f"{ctx.author.mention}, você tem **{balance} moedas**.",
        color=discord.Color.green()
    )
    embed.set_footer(text="CZP • Sistema de Moedas")

    await ctx.send(embed=embed, delete_after=PUBLIC_DELETE_DELAY)


@bot.command()
async def shop(ctx):
    await delete_command_message(ctx)

    header_embed = discord.Embed(
        title="🛒 Loja CZP",
        description=(
            "Confira os itens disponíveis abaixo.\n\n"
            "**Como comprar:** `!buy número`\n"
            "**Como ver saldo:** `!coins`"
        ),
        color=discord.Color.blurple()
    )
    header_embed.set_footer(text="CZP Store • Apoie o servidor")
    await ctx.send(embed=header_embed, delete_after=PUBLIC_DELETE_DELAY)

    categories = {}
    for item_id, item in SHOP_ITEMS.items():
        category = item["category"]
        if category not in categories:
            categories[category] = []
        categories[category].append((item_id, item))

    for category, items in categories.items():
        embed = discord.Embed(
            title=category,
            color=discord.Color.blue()
        )

        lines = []
        for item_id, item in items:
            lines.append(
                f"**{item_id}** • {item['name']} — **{item['price']} moedas**\n"
                f"> {item['desc']}"
            )

        embed.description = "\n\n".join(lines)
        embed.set_footer(text="Use !buy número")
        await ctx.send(embed=embed, delete_after=PUBLIC_DELETE_DELAY)


@bot.command()
@commands.has_permissions(administrator=True)
async def addcoins(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        await ctx.send("❌ O valor precisa ser maior que 0.")
        return

    add_user_coins(member.id, amount)
    new_balance = get_user_balance(member.id)

    embed = discord.Embed(
        title="✅ Moedas Adicionadas",
        description=f"Foram adicionadas **{amount} moedas** para {member.mention}.",
        color=discord.Color.gold()
    )
    embed.add_field(name="Novo saldo", value=f"{new_balance} moedas", inline=False)
    embed.set_footer(text="Comando administrativo")

    await ctx.send(embed=embed)

    await send_dm_receipt(
        member,
        "💰 Moedas Adicionadas",
        f"Você recebeu **{amount} moedas**.",
        fields=[
            ("Novo saldo", f"{new_balance} moedas", False)
        ],
        color=discord.Color.gold()
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def removecoins(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        await ctx.send("❌ O valor precisa ser maior que 0.")
        return

    balance = get_user_balance(member.id)

    if balance < amount:
        await ctx.send(
            f"❌ {member.mention} não tem moedas suficientes.\n"
            f"Saldo atual: **{balance} moedas**."
        )
        return

    remove_user_coins(member.id, amount)
    new_balance = get_user_balance(member.id)

    embed = discord.Embed(
        title="🗑️ Moedas Removidas",
        description=f"Foram removidas **{amount} moedas** de {member.mention}.",
        color=discord.Color.red()
    )
    embed.add_field(name="Novo saldo", value=f"{new_balance} moedas", inline=False)
    embed.set_footer(text="Comando administrativo")

    await ctx.send(embed=embed)

    await send_dm_receipt(
        member,
        "🗑️ Moedas Removidas",
        f"Foram removidas **{amount} moedas** da sua conta.",
        fields=[
            ("Novo saldo", f"{new_balance} moedas", False)
        ],
        color=discord.Color.red()
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def balance(ctx, member: discord.Member):
    balance_value = get_user_balance(member.id)

    embed = discord.Embed(
        title="📊 Saldo do Jogador",
        description=f"{member.mention} tem **{balance_value} moedas**.",
        color=discord.Color.purple()
    )
    embed.set_footer(text="Consulta administrativa")

    await ctx.send(embed=embed)


@bot.command()
async def buy(ctx, item: int):
    await delete_command_message(ctx)

    if item not in SHOP_ITEMS:
        await ctx.send(
            "❌ Item inválido. Use `!shop` para ver os itens.",
            delete_after=PUBLIC_DELETE_DELAY
        )
        return

    selected_item = SHOP_ITEMS[item]
    price = selected_item["price"]
    item_name = selected_item["name"]

    success = remove_user_coins(ctx.author.id, price)

    if not success:
        balance = get_user_balance(ctx.author.id)

        embed = discord.Embed(
            title="❌ Moedas Insuficientes",
            description=f"Você não tem moedas suficientes para comprar **{item_name}**.",
            color=discord.Color.red()
        )
        embed.add_field(name="Seu saldo atual", value=f"{balance} moedas", inline=False)

        await ctx.send(embed=embed, delete_after=PUBLIC_DELETE_DELAY)
        return

    new_balance = get_user_balance(ctx.author.id)

    embed = discord.Embed(
        title="✅ Compra Realizada",
        description=f"Você comprou **{item_name}** com sucesso.",
        color=discord.Color.green()
    )
    embed.add_field(name="Custo", value=f"{price} moedas", inline=True)
    embed.add_field(name="Saldo restante", value=f"{new_balance} moedas", inline=True)
    embed.set_footer(text="Seu pedido foi registrado")

    await ctx.send(embed=embed, delete_after=PUBLIC_DELETE_DELAY)

    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
    if admin_channel:
        admin_embed = discord.Embed(
            title="📦 Nova Compra",
            description="Um jogador realizou uma compra.",
            color=discord.Color.orange()
        )
        admin_embed.add_field(name="Player", value=ctx.author.mention, inline=False)
        admin_embed.add_field(name="Discord ID", value=str(ctx.author.id), inline=False)
        admin_embed.add_field(name="Item", value=item_name, inline=False)
        admin_embed.add_field(name="Custo", value=f"{price} moedas", inline=True)
        admin_embed.add_field(name="Saldo restante", value=f"{new_balance} moedas", inline=True)
        admin_embed.set_footer(text="CZP • Log de Compras")

        await admin_channel.send(embed=admin_embed)

    dm_sent = await send_dm_receipt(
        ctx.author,
        "🧾 Recibo de Compra",
        "Sua compra foi registrada com sucesso.",
        fields=[
            ("Item", item_name, False),
            ("Custo", f"{price} moedas", True),
            ("Saldo restante", f"{new_balance} moedas", True)
        ],
        color=discord.Color.green()
    )

    if not dm_sent:
        await ctx.send(
            f"{ctx.author.mention}, não consegui te enviar DM. Ative suas mensagens privadas para receber o recibo.",
            delete_after=PUBLIC_DELETE_DELAY
        )


@bot.command()
@commands.has_permissions(administrator=True)
async def reward(ctx, member: discord.Member, amount: int, *, reason="Evento"):
    if amount <= 0:
        await ctx.send("❌ Valor inválido.")
        return

    add_user_coins(member.id, amount)
    new_balance = get_user_balance(member.id)

    embed = discord.Embed(
        title="🏆 Evento Finalizado!",
        description=f"{member.mention} venceu o evento!",
        color=discord.Color.gold()
    )
    embed.add_field(name="Recompensa", value=f"{amount} moedas", inline=True)
    embed.add_field(name="Motivo", value=reason, inline=True)
    embed.set_footer(text="CZP • Recompensa de Evento")

    await ctx.send(embed=embed, delete_after=PUBLIC_DELETE_DELAY)

    await send_dm_receipt(
        member,
        "🏆 Vitória em Evento",
        "Você recebeu uma recompensa por vencer um evento.",
        fields=[
            ("Motivo", reason, False),
            ("Recompensa", f"{amount} moedas", True),
            ("Novo saldo", f"{new_balance} moedas", True)
        ],
        color=discord.Color.gold()
    )

    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
    if admin_channel:
        log_embed = discord.Embed(
            title="📊 Recompensa de Evento",
            description="Moedas adicionadas por vitória em evento.",
            color=discord.Color.orange()
        )
        log_embed.add_field(name="Player", value=member.mention, inline=False)
        log_embed.add_field(name="Discord ID", value=str(member.id), inline=False)
        log_embed.add_field(name="Moedas", value=str(amount), inline=True)
        log_embed.add_field(name="Motivo", value=reason, inline=True)
        log_embed.add_field(name="Novo saldo", value=f"{new_balance} moedas", inline=False)
        log_embed.set_footer(text="CZP • Log de Eventos")

        await admin_channel.send(embed=log_embed)


@bot.command()
@commands.has_permissions(administrator=True)
async def giveall(ctx, amount: int, *, reason="Recompensa geral"):
    if amount <= 0:
        await ctx.send("❌ Valor inválido.")
        return

    status_msg = await ctx.send(f"⏳ Distribuindo **{amount} moedas** para todos...")

    count = 0
    for member in ctx.guild.members:
        if member.bot:
            continue

        add_user_coins(member.id, amount)
        count += 1

    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
    if admin_channel:
        embed = discord.Embed(
            title="🌍 Recompensa Global",
            description="Moedas distribuídas para todos os jogadores.",
            color=discord.Color.gold()
        )
        embed.add_field(name="Quantidade", value=f"{amount} moedas", inline=True)
        embed.add_field(name="Jogadores afetados", value=str(count), inline=True)
        embed.add_field(name="Motivo", value=reason, inline=False)
        embed.set_footer(text="CZP • Log Global")

        await admin_channel.send(embed=embed)

    await status_msg.edit(content=f"✅ {count} jogadores receberam **{amount} moedas**.")


# =========================
# ERROR HANDLING
# =========================
@addcoins.error
async def addcoins_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Você não tem permissão para usar esse comando.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Uso correto: `!addcoins @usuario quantidade`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Verifique se marcou o usuário corretamente e usou um número válido.")


@removecoins.error
async def removecoins_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Você não tem permissão para usar esse comando.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Uso correto: `!removecoins @usuario quantidade`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Verifique se marcou o usuário corretamente e usou um número válido.")


@buy.error
async def buy_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Uso correto: `!buy número_do_item`", delete_after=PUBLIC_DELETE_DELAY)
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ O número do item precisa ser um número. Exemplo: `!buy 1`", delete_after=PUBLIC_DELETE_DELAY)


@balance.error
async def balance_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Você não tem permissão para usar esse comando.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Uso correto: `!balance @usuario`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Verifique se marcou o usuário corretamente.")


@reward.error
async def reward_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Você não tem permissão para usar esse comando.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Uso correto: `!reward @usuario quantidade motivo`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Verifique se marcou o usuário corretamente e usou uma quantidade válida.")


@giveall.error
async def giveall_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Você não tem permissão para usar esse comando.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Uso correto: `!giveall quantidade motivo`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Use uma quantidade válida. Exemplo: `!giveall 50 Evento global`")


bot.run(BOT_TOKEN)