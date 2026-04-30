import json
import os
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord import ui
from dotenv import load_dotenv

# =========================
# CONFIGURAÇÃO
# =========================
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(script_dir, ".env"))

TOKEN = os.getenv("BOT_TOKEN")

# COLOQUE AQUI O ID DO CANAL "Pedidos VIP"
ADMIN_CHANNEL_ID = 1487729614976712704

if not TOKEN:
    raise ValueError("BOT_TOKEN não foi encontrado no arquivo .env")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# BANCO DE DADOS
# =========================
DATA_FILE = os.path.join(script_dir, "coins.json")
STARTER_FILE = os.path.join(script_dir, "starter_claims.json")
ORDERS_FILE = os.path.join(script_dir, "orders.json")

PIX_CODE = """00020126580014br.gov.bcb.pix013696f850dd-18da-4a87-a008-51e6a9f1e1c95204000053039865802BR5919YGOR ATTILA DE LIMA6009Sao Paulo62290525REC69D91E76AB4C03429651466304A923"""
PIX_QR_FILE = os.path.join(script_dir, "pix_qr.png")


def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_starter_claims():
    try:
        with open(STARTER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def save_starter_claims(data):
    with open(STARTER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_orders():
    try:
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def save_orders(data):
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# =========================
# ITENS DA LOJA
# =========================
SHOP_CATEGORIES = {
    "🧱 Construção": {
        1: {"name": "Caixa de Pregos", "czp": 300},
        9: {"name": "Pacote de Tábuas (30)", "czp": 400},
        16: {"name": "Serrote", "czp": 150},
        15: {"name": "CodeLock", "czp": 450},
        12: {"name": "Bandeira", "czp": 300},
        13: {"name": "Kit de Território", "czp": 800},
        14: {"name": "Chapa de Metal 10", "czp": 1800},
        19: {"name": "Massa Epóxi", "czp": 250},
        30: {"name": "Cimento (2und.)", "czp": 400},
        31: {"name": "Mortar Mix (2und.)", "czp": 400}
    },

    "📦 Armazenamento": {
        20: {"name": "Container Pequeno", "czp": 300},
        21: {"name": "Container Médio", "czp": 500},
        22: {"name": "Armário Militar Grande", "czp": 850}
    },

    "🚗 Veículos": {
        4: {"name": "Chave de Carro", "czp": 1000},
        5: {"name": "Lock Pick de Carro", "czp": 3000},
        6: {"name": "BMW M5", "czp": 5000},
        7: {"name": "Ford F350", "czp": 2800},
        8: {"name": "Roda Ford F350", "czp": 400},
        23: {"name": "Bateria de Carro", "czp": 500},
        24: {"name": "Radiador", "czp": 600},
        25: {"name": "Vela de Ignição", "czp": 350},
        26: {"name": "Galão de Gasolina", "czp": 450},
        27: {"name": "Pneu de Carro", "czp": 400},
        28: {"name": "Roda BMW", "czp": 400}
    },

    "🎒 Equipamentos": {
        2: {"name": "Machadinha", "czp": 200},
        3: {"name": "Pedra de Amolar", "czp": 250},
        10: {"name": "Kit Inicial", "czp": 500},
        11: {"name": "Mochila MMG 120", "czp": 900},
        29: {"name": "Kit NBC Completo", "czp": 400}
    },

    "🪖 MMG Gear": {
        17: {"name": "Set Militar MMG Alpine", "czp": 1500}
    },

    "⚡ VIP & Serviços": {
        18: {"name": "Prioridade na Fila - 30 Dias", "czp": 1200}
    }
}

# Mantém compatibilidade com toda a lógica original
SHOP_ITEMS = {}
for category in SHOP_CATEGORIES.values():
    SHOP_ITEMS.update(category)

# =========================
# PACOTES DE CZP
# =========================
CZP_PACKAGES = {
    "starter": {
        "name": "Grátis - Saldo Inicial",
        "price_brl": "R$ 0,00",
        "czp": 1500,
        "bonus": "Disponível a cada 365 dias"
    },
    "p1": {
        "name": "Starter Pack",
        "price_brl": "R$ 5,00",
        "czp": 500,
        "bonus": "Starter Pack"
    },
    "p2": {
        "name": "Standard Rate",
        "price_brl": "R$ 10,00",
        "czp": 1000,
        "bonus": "Taxa padrão"
    },
    "p3": {
        "name": "5% Bonus Included",
        "price_brl": "R$ 20,00",
        "czp": 2100,
        "bonus": "5% de bônus incluso"
    },
    "p4": {
        "name": "10% Bonus Included",
        "price_brl": "R$ 50,00",
        "czp": 5500,
        "bonus": "10% de bônus incluso"
    },
    "p5": {
        "name": "20% Bonus (Best Value)",
        "price_brl": "R$ 100,00",
        "czp": 12000,
        "bonus": "20% de bônus - Melhor custo benefício"
    }
}


# =========================
# FUNÇÕES AUXILIARES
# =========================
def get_balance(user_id: int) -> int:
    data = load_data()
    return int(data.get(str(user_id), 0))


def remove_balance(user_id: int, amount: int) -> bool:
    data = load_data()
    uid = str(user_id)

    current_balance = int(data.get(uid, 0))
    if current_balance < amount:
        return False

    data[uid] = current_balance - amount
    save_data(data)
    return True


def add_balance(user_id: int, amount: int):
    data = load_data()
    uid = str(user_id)
    data[uid] = int(data.get(uid, 0)) + amount
    save_data(data)


async def send_dm_safe(user: discord.User | discord.Member, embed: discord.Embed):
    try:
        await user.send(embed=embed)
        return True
    except discord.Forbidden:
        return False
    except discord.HTTPException:
        return False


async def send_dm_with_pix(user: discord.User | discord.Member, embed: discord.Embed):
    try:
        if os.path.exists(PIX_QR_FILE):
            file = discord.File(PIX_QR_FILE, filename="pix_qr.png")
            embed.set_image(url="attachment://pix_qr.png")
            await user.send(embed=embed, file=file)
        else:
            await user.send(embed=embed)
        return True
    except discord.Forbidden:
        return False
    except discord.HTTPException:
        return False


def generate_order_id():
    return datetime.now().strftime("CZP%Y%m%d%H%M%S")


def build_shop_embed():
    embed = discord.Embed(
        title="🏪 MERCADO CZP",
        description="Use os botões abaixo para comprar itens ou consultar seu saldo.",
        color=0x00FF88
    )

    for category_name, items in SHOP_CATEGORIES.items():
        value = ""
        for item_id, item in items.items():
            value += f"ID {item_id} • {item['name']} • {item['czp']} CZP\n"

        embed.add_field(
            name=category_name,
            value=value,
            inline=False
        )

    embed.set_footer(text="Carnage Z Store System")
    return embed


def build_czp_packages_embed():
    embed = discord.Embed(
        title="💳 Adquirir CZP",
        description="Escolha abaixo um pacote de CZP para solicitar.",
        color=0xFFD700
    )

    embed.add_field(
        name="🎁 Grátis",
        value="**Grátis - Saldo Inicial**\n1500 CZP\nDisponível 1 vez a cada 365 dias",
        inline=False
    )

    embed.add_field(
        name="💰 Pacotes pagos",
        value=(
            "**R$ 5,00** • 500 CZP • Starter Pack\n"
            "**R$ 10,00** • 1.000 CZP • Standard Rate\n"
            "**R$ 20,00** • 2.100 CZP • 5% Bonus included\n"
            "**R$ 50,00** • 5.500 CZP • 10% Bonus included\n"
            "**R$ 100,00** • 12.000 CZP • 20% Bonus (Best Value)"
        ),
        inline=False
    )

    embed.set_footer(text="Carnage Z CZP Store")
    return embed


# =========================
# MODAL DE COMPRA
# =========================
class PurchaseModal(ui.Modal, title="Finalizar Compra"):
    def __init__(self, selected_item_id: int):
        super().__init__()
        self.selected_item_id = selected_item_id

        self.nickname = ui.TextInput(
            label="Nickname in-game",
            placeholder="Digite seu nickname no servidor",
            min_length=2,
            max_length=32
        )

        self.item_id_input = ui.TextInput(
            label="ID do Item",
            placeholder=f"Confirme o ID do item ({selected_item_id})",
            min_length=1,
            max_length=3
        )

        self.quantity = ui.TextInput(
            label="Quantidade",
            placeholder="Ex: 1",
            default="1",
            min_length=1,
            max_length=3
        )

        self.add_item(self.nickname)
        self.add_item(self.item_id_input)
        self.add_item(self.quantity)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            typed_item_id = int(self.item_id_input.value.strip())
            quantity = int(self.quantity.value.strip())
        except ValueError:
            await interaction.followup.send(
                "❌ ID do item e quantidade precisam ser números.",
                ephemeral=True
            )
            return

        if quantity <= 0:
            await interaction.followup.send(
                "❌ A quantidade precisa ser maior que 0.",
                ephemeral=True
            )
            return

        if typed_item_id != self.selected_item_id:
            await interaction.followup.send(
                f"❌ O ID digitado não corresponde ao item escolhido. Você selecionou o item **{self.selected_item_id}**.",
                ephemeral=True
            )
            return

        item = SHOP_ITEMS.get(typed_item_id)
        if not item:
            await interaction.followup.send("❌ Item inválido.", ephemeral=True)
            return

        total_price = item["czp"] * quantity
        current_balance = get_balance(interaction.user.id)

        if current_balance < total_price:
            await interaction.followup.send(
                f"❌ Saldo insuficiente.\n"
                f"Seu saldo atual: **{current_balance} CZP**\n"
                f"Total da compra: **{total_price} CZP**",
                ephemeral=True
            )
            return

        success = remove_balance(interaction.user.id, total_price)
        if not success:
            await interaction.followup.send(
                "❌ Não foi possível descontar o saldo. Tente novamente.",
                ephemeral=True
            )
            return

        new_balance = get_balance(interaction.user.id)
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        buyer_embed = discord.Embed(
            title="🧾 Recibo de Compra - CZP Store",
            color=0x00FF88,
            timestamp=datetime.now()
        )
        buyer_embed.add_field(name="Comprador", value=interaction.user.mention, inline=False)
        buyer_embed.add_field(name="Nickname in-game", value=self.nickname.value, inline=False)
        buyer_embed.add_field(name="Item", value=item["name"], inline=False)
        buyer_embed.add_field(name="ID do Item", value=str(typed_item_id), inline=True)
        buyer_embed.add_field(name="Quantidade", value=str(quantity), inline=True)
        buyer_embed.add_field(name="Total", value=f"{total_price} CZP", inline=True)
        buyer_embed.add_field(name="Saldo restante", value=f"{new_balance} CZP", inline=False)
        buyer_embed.set_footer(text=f"Pedido realizado em {timestamp}")

        dm_sent = await send_dm_safe(interaction.user, buyer_embed)

        admin_embed = discord.Embed(
            title="📦 Novo Pedido VIP",
            color=0xFFD700,
            timestamp=datetime.now()
        )
        admin_embed.add_field(name="Usuário", value=f"{interaction.user} ({interaction.user.id})", inline=False)
        admin_embed.add_field(name="Nickname in-game", value=self.nickname.value, inline=False)
        admin_embed.add_field(name="Item", value=item["name"], inline=False)
        admin_embed.add_field(name="ID do Item", value=str(typed_item_id), inline=True)
        admin_embed.add_field(name="Quantidade", value=str(quantity), inline=True)
        admin_embed.add_field(name="Total pago", value=f"{total_price} CZP", inline=True)
        admin_embed.add_field(name="Saldo restante do usuário", value=f"{new_balance} CZP", inline=False)

        admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
        if admin_channel:
            await admin_channel.send(embed=admin_embed)

        msg = (
            f"✅ Compra registrada com sucesso.\n"
            f"Item: **{item['name']}**\n"
            f"Quantidade: **{quantity}**\n"
            f"Total: **{total_price} CZP**\n"
            f"Saldo restante: **{new_balance} CZP**"
        )

        if dm_sent:
            msg += "\n📩 Um recibo foi enviado na sua DM."
        else:
            msg += "\n⚠️ Não consegui enviar DM. Verifique se suas mensagens privadas estão abertas."

        await interaction.followup.send(msg, ephemeral=True)


# =========================
# SELECT MENU
# =========================
class ItemSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=f"{item_id} - {item['name']}",
                description=f"Custo: {item['czp']} CZP",
                value=str(item_id)
            )
            for item_id, item in SHOP_ITEMS.items()
        ]

        super().__init__(
            placeholder="Selecione um item para comprar",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_item_id = int(self.values[0])
        await interaction.response.send_modal(PurchaseModal(selected_item_id))


class BuySelectView(ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(ItemSelect())


# =========================
# SELECT MENU - ADQUIRIR CZP
# =========================
class AdminCZPOrderView(ui.View):
    def __init__(self, order_id: str):
        super().__init__(timeout=None)
        self.order_id = order_id

    @ui.button(label="✅ Confirmar Pagamento", style=discord.ButtonStyle.success)
    async def confirm_payment(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem usar este botão.", ephemeral=True)
            return

        orders = load_orders()
        order = orders.get(self.order_id)

        if not order:
            await interaction.response.send_message("❌ Pedido não encontrado.", ephemeral=True)
            return

        if order["status"] != "Aguardando pagamento":
            await interaction.response.send_message(f"⚠️ Este pedido já está marcado como: **{order['status']}**", ephemeral=True)
            return

        user_id = int(order["user_id"])
        amount = int(order["czp"])

        add_balance(user_id, amount)
        new_balance = get_balance(user_id)

        order["status"] = "Pagamento confirmado"
        order["confirmed_by"] = str(interaction.user)
        order["confirmed_at"] = datetime.now().isoformat()
        orders[self.order_id] = order
        save_orders(orders)

        try:
            user = await bot.fetch_user(user_id)

            receipt_embed = discord.Embed(
                title="✅ Pagamento Confirmado",
                description="Seu pagamento foi confirmado e o CZP foi adicionado.",
                color=0x2ECC71,
                timestamp=datetime.now()
            )
            receipt_embed.add_field(name="Pedido", value=self.order_id, inline=False)
            receipt_embed.add_field(name="CZP adicionado", value=f"{amount} CZP", inline=False)
            receipt_embed.add_field(name="Saldo atual", value=f"{new_balance} CZP", inline=False)
            receipt_embed.set_footer(text="Carnage Z CZP")

            await send_dm_safe(user, receipt_embed)
        except discord.HTTPException:
            pass

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(view=self)

        await interaction.response.send_message(
            f"✅ Pagamento confirmado.\n"
            f"Foram adicionados **{amount} CZP** ao usuário <@{user_id}>.\n"
            f"Novo saldo: **{new_balance} CZP**",
            ephemeral=True
        )

    @ui.button(label="❌ Cancelar Pedido", style=discord.ButtonStyle.danger)
    async def cancel_payment(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem usar este botão.", ephemeral=True)
            return

        orders = load_orders()
        order = orders.get(self.order_id)

        if not order:
            await interaction.response.send_message("❌ Pedido não encontrado.", ephemeral=True)
            return

        if order["status"] != "Aguardando pagamento":
            await interaction.response.send_message(f"⚠️ Este pedido já está marcado como: **{order['status']}**", ephemeral=True)
            return

        order["status"] = "Pedido cancelado"
        order["cancelled_by"] = str(interaction.user)
        order["cancelled_at"] = datetime.now().isoformat()
        orders[self.order_id] = order
        save_orders(orders)

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(view=self)

        await interaction.response.send_message(
            f"❌ Pedido `{self.order_id}` cancelado.",
            ephemeral=True
        )


class CZPPackageSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Grátis - Saldo Inicial",
                description="1500 CZP • disponível a cada 365 dias",
                value="starter"
            ),
            discord.SelectOption(
                label="R$ 5,00 • 500 CZP",
                description="Pacote Inicial",
                value="p1"
            ),
            discord.SelectOption(
                label="R$ 10,00 • 1.000 CZP",
                description="Preço Base",
                value="p2"
            ),
            discord.SelectOption(
                label="R$ 20,00 • 2.100 CZP",
                description="5% de bônus incluído",
                value="p3"
            ),
            discord.SelectOption(
                label="R$ 50,00 • 5.500 CZP",
                description="+10% de Bônus",
                value="p4"
            ),
            discord.SelectOption(
                label="R$ 100,00 • 12.000 CZP",
                description="+20% de Bônus (Mais Vantajoso)",
                value="p5"
            ),
        ]

        super().__init__(
            placeholder="Selecione um pacote de CZP",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_package_id = self.values[0]
        package = CZP_PACKAGES[selected_package_id]

        # PACOTE GRÁTIS COM COOLDOWN DE 365 DIAS
        if selected_package_id == "starter":
            claims = load_starter_claims()
            uid = str(interaction.user.id)
            now = datetime.now()

            if uid in claims:
                last_claim = datetime.fromisoformat(claims[uid])
                cooldown = timedelta(days=365)

                if now - last_claim < cooldown:
                    remaining = cooldown - (now - last_claim)
                    days = remaining.days
                    hours = remaining.seconds // 3600

                    await interaction.response.send_message(
                        f"❌ Você já resgatou seu saldo inicial.\n"
                        f"Tente novamente em **{days} dias e {hours} horas**.",
                        ephemeral=True
                    )
                    return

            add_balance(interaction.user.id, package["czp"])
            claims[uid] = now.isoformat()
            save_starter_claims(claims)

            new_balance = get_balance(interaction.user.id)

            free_embed = discord.Embed(
                title="🎁 Recibo de Resgate CZP",
                description="Seu saldo inicial foi liberado com sucesso.",
                color=0x2ECC71,
                timestamp=datetime.now()
            )
            free_embed.add_field(
                name="Pacote",
                value=f"{package['name']} - {package['czp']} CZP",
                inline=False
            )
            free_embed.add_field(
                name="Saldo atual",
                value=f"{new_balance} CZP",
                inline=False
            )
            free_embed.set_footer(text="Carnage Z CZP")

            await send_dm_safe(interaction.user, free_embed)

            admin_embed = discord.Embed(
                title="🎁 Resgate de CZP Grátis",
                color=0x2ECC71,
                timestamp=datetime.now()
            )
            admin_embed.add_field(
                name="Usuário",
                value=f"{interaction.user} ({interaction.user.id})",
                inline=False
            )
            admin_embed.add_field(
                name="Pacote",
                value=f"{package['name']} - {package['czp']} CZP",
                inline=False
            )
            admin_embed.add_field(
                name="Novo saldo",
                value=f"{new_balance} CZP",
                inline=False
            )

            admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
            if admin_channel:
                await admin_channel.send(embed=admin_embed)

            await interaction.response.send_message(
                f"✅ Você recebeu **{package['czp']} CZP** grátis.\n"
                f"Seu novo saldo é **{new_balance} CZP**.",
                ephemeral=True
            )
            return

        # PACOTES PAGOS → ENVIA PIX E REGISTRA PEDIDO PARA O ADMIN
        order_id = generate_order_id()

        orders = load_orders()
        orders[order_id] = {
            "order_id": order_id,
            "user_id": str(interaction.user.id),
            "user_name": str(interaction.user),
            "package": package["name"],
            "price_brl": package["price_brl"],
            "czp": package["czp"],
            "bonus": package["bonus"],
            "status": "Aguardando pagamento",
            "created_at": datetime.now().isoformat()
        }
        save_orders(orders)

        payment_embed = discord.Embed(
            title="💳 Pagamento via PIX - CZP",
            description=(
                f"**Pedido:** `{order_id}`\n\n"
                f"Você selecionou o pacote **{package['name']}**.\n\n"
                f"**Valor:** {package['price_brl']}\n"
                f"**CZP:** {package['czp']} CZP\n"
                f"**Detalhe:** {package['bonus']}\n\n"
                f"Faça o pagamento via PIX usando o QR Code ou copie o código abaixo."
            ),
            color=0x00C853,
            timestamp=datetime.now()
        )

        payment_embed.add_field(
            name="📋 Código PIX Copia e Cola",
            value=f"```{PIX_CODE}```",
            inline=False
        )

        payment_embed.add_field(
            name="🧾 Instruções",
            value=(
                "1. Faça o pagamento do valor exato\n"
                "2. Guarde o comprovante\n"
                "3. Envie o comprovante para a equipe/admin via ticket\n"
                "4. Após confirmação, seu saldo CZP será adicionado"
            ),
            inline=False
        )

        payment_embed.set_footer(text="Carnage Z • Pagamento CZP")

        dm_sent = await send_dm_with_pix(interaction.user, payment_embed)

        admin_embed = discord.Embed(
            title="💳 Novo Pedido de CZP",
            description="Pedido aguardando pagamento/confirmação.",
            color=0xFFD700,
            timestamp=datetime.now()
        )
        admin_embed.add_field(
            name="Pedido",
            value=order_id,
            inline=False
        )
        admin_embed.add_field(
            name="Usuário",
            value=f"{interaction.user} ({interaction.user.id})",
            inline=False
        )
        admin_embed.add_field(
            name="Pacote",
            value=package["name"],
            inline=False
        )
        admin_embed.add_field(
            name="Valor",
            value=package["price_brl"],
            inline=True
        )
        admin_embed.add_field(
            name="CZP",
            value=f"{package['czp']} CZP",
            inline=True
        )
        admin_embed.add_field(
            name="Observação",
            value=package["bonus"],
            inline=False
        )
        admin_embed.add_field(
            name="Status",
            value="Aguardando pagamento",
            inline=False
        )

        admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
        if admin_channel:
            await admin_channel.send(
                embed=admin_embed,
                view=AdminCZPOrderView(order_id)
            )

        user_msg = (
            f"✅ Seu pedido foi criado com sucesso.\n"
            f"**Pacote:** {package['name']}\n"
            f"**Valor:** {package['price_brl']}\n"
            f"**CZP:** {package['czp']} CZP\n\n"
        )

        if dm_sent:
            user_msg += "📩 Enviei o QR Code e o código PIX na sua DM."
        else:
            user_msg += (
                "⚠️ Não consegui enviar DM.\n"
                "Abra sua DM e tente novamente, ou fale com a equipe."
            )

        await interaction.response.send_message(user_msg, ephemeral=True)


class CZPPackageView(ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(CZPPackageSelect())


# =========================
# BOTÕES PRINCIPAIS
# =========================
class MainShopView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🛒 Comprar", style=discord.ButtonStyle.success, custom_id="czp_buy_button")
    async def buy_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            "Selecione abaixo o item que você quer comprar:",
            view=BuySelectView(),
            ephemeral=True
        )

    @ui.button(label="💰 Ver saldo", style=discord.ButtonStyle.primary, custom_id="czp_balance_button")
    async def balance_button(self, interaction: discord.Interaction, button: ui.Button):
        balance = get_balance(interaction.user.id)

        balance_embed = discord.Embed(
            title="💰 Saldo CZP",
            description=f"Seu saldo atual é **{balance} CZP**",
            color=0x3498DB,
            timestamp=datetime.now()
        )
        balance_embed.set_footer(text="Carnage Z Coins")

        dm_sent = await send_dm_safe(interaction.user, balance_embed)

        if dm_sent:
            await interaction.response.send_message(
                "📩 Enviei seu saldo na DM.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"⚠️ Não consegui te mandar DM.\nSeu saldo atual é **{balance} CZP**",
                ephemeral=True
            )

    @ui.button(label="💳 Adquirir CZP", style=discord.ButtonStyle.secondary, custom_id="czp_acquire_button")
    async def acquire_czp_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            embed=build_czp_packages_embed(),
            view=CZPPackageView(),
            ephemeral=True
        )


# =========================
# EVENTOS
# =========================
@bot.event
async def on_ready():
    bot.add_view(MainShopView())
    print(f"✅ Bot online como {bot.user}")


# =========================
# COMANDO ADMIN PARA POSTAR A LOJA
# =========================
@bot.command()
@commands.has_permissions(administrator=True)
async def setup_shop(ctx):
    embed = build_shop_embed()
    await ctx.send(embed=embed, view=MainShopView())


# =========================
# COMANDOS ADMIN DE MOEDAS
# =========================
@bot.command()
@commands.has_permissions(administrator=True)
async def addcoins(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        await ctx.send("❌ O valor precisa ser maior que 0.")
        return

    data = load_data()
    uid = str(member.id)
    data[uid] = int(data.get(uid, 0)) + amount
    save_data(data)

    await ctx.send(f"✅ {amount} CZP adicionados para {member.mention}. Saldo atual: **{data[uid]} CZP**")


@bot.command()
@commands.has_permissions(administrator=True)
async def setcoins(ctx, member: discord.Member, amount: int):
    if amount < 0:
        await ctx.send("❌ O valor não pode ser negativo.")
        return

    data = load_data()
    data[str(member.id)] = amount
    save_data(data)

    await ctx.send(f"✅ Saldo de {member.mention} definido para **{amount} CZP**")


@bot.command()
@commands.has_permissions(administrator=True)
async def saldo(ctx, member: discord.Member = None):
    member = member or ctx.author
    balance = get_balance(member.id)
    await ctx.send(f"💰 Saldo de {member.mention}: **{balance} CZP**")


@bot.command()
@commands.has_permissions(administrator=True)
async def addall(ctx, amount: int):
    if amount <= 0:
        await ctx.send("❌ O valor precisa ser maior que 0.")
        return

    data = load_data()

    if not data:
        await ctx.send("⚠️ Nenhum usuário encontrado no banco de dados.")
        return

    for user_id in data:
        data[user_id] = int(data.get(user_id, 0)) + amount

    save_data(data)
    await ctx.send(f"✅ {amount} CZP adicionados para TODOS os usuários cadastrados.")


@bot.command()
@commands.has_permissions(administrator=True)
async def removeall(ctx, amount: int):
    if amount <= 0:
        await ctx.send("❌ O valor precisa ser maior que 0.")
        return

    data = load_data()

    if not data:
        await ctx.send("⚠️ Nenhum usuário encontrado no banco de dados.")
        return

    for user_id in data:
        current_balance = int(data.get(user_id, 0))
        data[user_id] = max(0, current_balance - amount)

    save_data(data)
    await ctx.send(f"💸 {amount} CZP removidos de TODOS os usuários cadastrados.")


@bot.command()
@commands.has_permissions(administrator=True)
async def resetall(ctx):
    data = load_data()

    if not data:
        await ctx.send("⚠️ Nenhum usuário para resetar.")
        return

    for user_id in data:
        data[user_id] = 0

    save_data(data)
    await ctx.send("♻️ Todos os saldos foram resetados para 0.")


@bot.command()
@commands.has_permissions(administrator=True)
async def removecoins(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        await ctx.send("❌ O valor precisa ser maior que 0.")
        return

    data = load_data()
    uid = str(member.id)
    current_balance = int(data.get(uid, 0))

    if current_balance <= 0:
        await ctx.send(f"⚠️ {member.mention} não tem CZP para remover.")
        return

    removed_amount = min(amount, current_balance)
    data[uid] = current_balance - removed_amount
    save_data(data)

    await ctx.send(
        f"💸 {removed_amount} CZP removidos de {member.mention}. "
        f"Saldo atual: **{data[uid]} CZP**"
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def confirmczp(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        await ctx.send("❌ O valor precisa ser maior que 0.")
        return

    add_balance(member.id, amount)
    new_balance = get_balance(member.id)

    await ctx.send(
        f"✅ Pagamento confirmado para {member.mention}.\n"
        f"Foram adicionados **{amount} CZP**.\n"
        f"Saldo atual: **{new_balance} CZP**"
    )

    receipt_embed = discord.Embed(
        title="✅ Pagamento Confirmado",
        description="Seu pagamento foi confirmado e o CZP foi adicionado.",
        color=0x2ECC71,
        timestamp=datetime.now()
    )
    receipt_embed.add_field(name="CZP adicionado", value=f"{amount} CZP", inline=False)
    receipt_embed.add_field(name="Saldo atual", value=f"{new_balance} CZP", inline=False)
    receipt_embed.set_footer(text="Carnage Z CZP")

    await send_dm_safe(member, receipt_embed)


# =========================
# LEADERBOARD
# =========================
@bot.command()
async def leaderboard(ctx):
    data = load_data()

    if not data:
        await ctx.send("⚠️ Ainda não há dados de saldo para mostrar.")
        return

    sorted_users = sorted(data.items(), key=lambda x: int(x[1]), reverse=True)
    top_users = sorted_users[:10]

    embed = discord.Embed(
        title="🏆 Leaderboard CZP",
        description="Top 10 jogadores com mais moedas",
        color=0xF1C40F,
        timestamp=datetime.now()
    )

    medal_emojis = ["🥇", "🥈", "🥉"]

    for index, (user_id, balance) in enumerate(top_users, start=1):
        member = ctx.guild.get_member(int(user_id))
        display_name = member.display_name if member else f"Usuário {user_id}"

        if index <= 3:
            prefix = medal_emojis[index - 1]
        else:
            prefix = f"#{index}"

        embed.add_field(
            name=f"{prefix} {display_name}",
            value=f"**{balance} CZP**",
            inline=False
        )

    embed.set_footer(text="Carnage Z Coins Ranking")
    await ctx.send(embed=embed)


bot.run(TOKEN)