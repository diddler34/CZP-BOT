import json
import os
import sqlite3
import threading
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
intents.presences = True  

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# BANCO DE DADOS SEGURO
# PostgreSQL no Railway / SQLite local
# =========================
# IMPORTANTE:
# - No Railway, crie um PostgreSQL e coloque DATABASE_URL nas Variables.
# - Se DATABASE_URL existir, o bot usa PostgreSQL.
# - Se DATABASE_URL não existir, ele usa SQLite local em carnagez_czp.db.
# - O SQLite local é bom para teste no PC, mas no Railway use PostgreSQL.

DATA_FILE = os.path.join(script_dir, "coins.json")  # arquivo antigo, usado só para migração automática
STARTER_FILE = os.path.join(script_dir, "starter_claims.json")  # arquivo antigo, usado só para migração automática
ORDERS_FILE = os.path.join(script_dir, "orders.json")  # arquivo antigo, usado só para migração automática
SQLITE_FILE = os.path.join(script_dir, "carnagez_czp.db")
DATABASE_URL = os.getenv("DATABASE_URL")

PIX_CODE = """00020126580014br.gov.bcb.pix013696f850dd-18da-4a87-a008-51e6a9f1e1c95204000053039865802BR5919YGOR ATTILA DE LIMA6009Sao Paulo62290525REC69D91E76AB4C03429651466304A923"""
PIX_QR_FILE = os.path.join(script_dir, "pix_qr.png")

DB_LOCK = threading.RLock()
DB_READY = False
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    try:
        import psycopg2
    except ImportError:
        raise ImportError(
            "DATABASE_URL foi encontrado, mas psycopg2-binary não está instalado. "
            "Adicione psycopg2-binary no requirements.txt."
        )


def _db_placeholder():
    return "%s" if USE_POSTGRES else "?"


def _connect_db():
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL)

    conn = sqlite3.connect(SQLITE_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _load_legacy_json(file_path: str, default=None):
    if default is None:
        default = {}
    try:
        if not os.path.exists(file_path):
            return default
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return default
            data = json.loads(content)
            return data if isinstance(data, dict) else default
    except Exception as e:
        print(f"⚠️ Não consegui migrar {os.path.basename(file_path)}: {e}")
        return default


def init_db():
    """Cria as tabelas e migra automaticamente os JSON antigos se o banco estiver vazio."""
    global DB_READY

    with DB_LOCK:
        if DB_READY:
            return True

        try:
            conn = _connect_db()
            cur = conn.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS balances (
                    user_id TEXT PRIMARY KEY,
                    balance INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS starter_claims (
                    user_id TEXT PRIMARY KEY,
                    claimed_at TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    status TEXT,
                    created_at TEXT,
                    data TEXT NOT NULL
                )
            """)

            cur.execute("SELECT COUNT(*) FROM balances")
            balance_count = cur.fetchone()[0]

            if balance_count == 0:
                old_balances = _load_legacy_json(DATA_FILE, {})
                if old_balances:
                    print(f"🔁 Migrando {len(old_balances)} saldos do coins.json para o banco de dados...")
                    p = _db_placeholder()
                    for user_id, balance in old_balances.items():
                        try:
                            cur.execute(
                                f"""
                                INSERT INTO balances (user_id, balance, updated_at)
                                VALUES ({p}, {p}, {p})
                                ON CONFLICT(user_id) DO UPDATE SET
                                    balance = excluded.balance,
                                    updated_at = excluded.updated_at
                                """,
                                (str(user_id), int(balance), datetime.now().isoformat())
                            )
                        except Exception as e:
                            print(f"⚠️ Saldo ignorado na migração: {user_id} -> {balance} | {e}")

            cur.execute("SELECT COUNT(*) FROM starter_claims")
            starter_count = cur.fetchone()[0]

            if starter_count == 0:
                old_claims = _load_legacy_json(STARTER_FILE, {})
                if old_claims:
                    print(f"🔁 Migrando {len(old_claims)} resgates iniciais para o banco de dados...")
                    p = _db_placeholder()
                    for user_id, claimed_at in old_claims.items():
                        cur.execute(
                            f"""
                            INSERT INTO starter_claims (user_id, claimed_at)
                            VALUES ({p}, {p})
                            ON CONFLICT(user_id) DO UPDATE SET claimed_at = excluded.claimed_at
                            """,
                            (str(user_id), str(claimed_at))
                        )

            cur.execute("SELECT COUNT(*) FROM orders")
            orders_count = cur.fetchone()[0]

            if orders_count == 0:
                old_orders = _load_legacy_json(ORDERS_FILE, {})
                if old_orders:
                    print(f"🔁 Migrando {len(old_orders)} pedidos para o banco de dados...")
                    p = _db_placeholder()
                    for order_id, order in old_orders.items():
                        if not isinstance(order, dict):
                            continue
                        cur.execute(
                            f"""
                            INSERT INTO orders (order_id, user_id, status, created_at, data)
                            VALUES ({p}, {p}, {p}, {p}, {p})
                            ON CONFLICT(order_id) DO UPDATE SET
                                user_id = excluded.user_id,
                                status = excluded.status,
                                created_at = excluded.created_at,
                                data = excluded.data
                            """,
                            (
                                str(order_id),
                                str(order.get("user_id", "")),
                                str(order.get("status", "")),
                                str(order.get("created_at", datetime.now().isoformat())),
                                json.dumps(order, ensure_ascii=False)
                            )
                        )

            conn.commit()
            cur.close()
            conn.close()
            DB_READY = True

            if USE_POSTGRES:
                print("✅ Banco de dados conectado: PostgreSQL")
            else:
                print(f"✅ Banco de dados conectado: SQLite local ({SQLITE_FILE})")

            return True

        except Exception as e:
            print(f"❌ Erro ao iniciar banco de dados: {e}")
            return False


def load_data():
    init_db()
    with DB_LOCK:
        try:
            conn = _connect_db()
            cur = conn.cursor()
            cur.execute("SELECT user_id, balance FROM balances")
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return {str(user_id): int(balance) for user_id, balance in rows}
        except Exception as e:
            print(f"⚠️ Erro ao carregar saldos do banco: {e}")
            return {}


def save_data(data):
    init_db()
    if data is None:
        return False

    with DB_LOCK:
        try:
            conn = _connect_db()
            cur = conn.cursor()
            p = _db_placeholder()
            now = datetime.now().isoformat()

            for user_id, balance in data.items():
                cur.execute(
                    f"""
                    INSERT INTO balances (user_id, balance, updated_at)
                    VALUES ({p}, {p}, {p})
                    ON CONFLICT(user_id) DO UPDATE SET
                        balance = excluded.balance,
                        updated_at = excluded.updated_at
                    """,
                    (str(user_id), int(balance), now)
                )

            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            print(f"⚠️ Erro ao salvar saldos no banco: {e}")
            return False


def get_balance(user_id: int) -> int:
    init_db()
    with DB_LOCK:
        try:
            conn = _connect_db()
            cur = conn.cursor()
            p = _db_placeholder()
            cur.execute(f"SELECT balance FROM balances WHERE user_id = {p}", (str(user_id),))
            row = cur.fetchone()
            cur.close()
            conn.close()
            return int(row[0]) if row else 0
        except Exception as e:
            print(f"?? Erro ao consultar saldo de {user_id}: {e}")
            return 0


def add_balance(user_id: int, amount: int) -> bool:
    init_db()
    if amount <= 0:
        return False

    with DB_LOCK:
        conn = None
        try:
            conn = _connect_db()
            cur = conn.cursor()
            p = _db_placeholder()
            uid = str(user_id)
            now = datetime.now().isoformat()

            cur.execute(
                f"""
                INSERT INTO balances (user_id, balance, updated_at)
                VALUES ({p}, {p}, {p})
                ON CONFLICT(user_id) DO UPDATE SET
                    balance = balances.balance + excluded.balance,
                    updated_at = excluded.updated_at
                """,
                (uid, int(amount), now)
            )

            conn.commit()
            cur.close()
            conn.close()
            print(f"?? ADD CZP | user={uid} | add={amount} | saldo={get_balance(user_id)}")
            return True
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            print(f"?? Erro ao adicionar saldo para {user_id}: {e}")
            return False


def remove_balance(user_id: int, amount: int) -> bool:
    init_db()
    if amount <= 0:
        return False

    with DB_LOCK:
        conn = None
        try:
            conn = _connect_db()
            cur = conn.cursor()
            p = _db_placeholder()
            uid = str(user_id)
            now = datetime.now().isoformat()

            cur.execute(
                f"""
                UPDATE balances
                SET balance = balance - {p}, updated_at = {p}
                WHERE user_id = {p} AND balance >= {p}
                """,
                (int(amount), now, uid, int(amount))
            )

            success = cur.rowcount == 1
            conn.commit()
            cur.close()
            conn.close()
            if success:
                print(f"?? REMOVE CZP | user={uid} | remove={amount} | saldo={get_balance(user_id)}")
            return success
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            print(f"?? Erro ao remover saldo de {user_id}: {e}")
            return False


def set_balance(user_id: int, amount: int) -> bool:
    init_db()
    if amount < 0:
        return False

    with DB_LOCK:
        conn = None
        try:
            conn = _connect_db()
            cur = conn.cursor()
            p = _db_placeholder()
            now = datetime.now().isoformat()
            cur.execute(
                f"""
                INSERT INTO balances (user_id, balance, updated_at)
                VALUES ({p}, {p}, {p})
                ON CONFLICT(user_id) DO UPDATE SET
                    balance = excluded.balance,
                    updated_at = excluded.updated_at
                """,
                (str(user_id), int(amount), now)
            )
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            print(f"?? Erro ao definir saldo de {user_id}: {e}")
            return False


def add_balance_all(amount: int) -> int:
    init_db()
    if amount <= 0:
        return 0

    with DB_LOCK:
        conn = None
        try:
            conn = _connect_db()
            cur = conn.cursor()
            p = _db_placeholder()
            now = datetime.now().isoformat()
            cur.execute(f"UPDATE balances SET balance = balance + {p}, updated_at = {p}", (int(amount), now))
            changed = cur.rowcount
            conn.commit()
            cur.close()
            conn.close()
            return changed
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            print(f"?? Erro ao adicionar saldo para todos: {e}")
            return 0


def remove_balance_all(amount: int) -> int:
    init_db()
    if amount <= 0:
        return 0

    with DB_LOCK:
        conn = None
        try:
            conn = _connect_db()
            cur = conn.cursor()
            p = _db_placeholder()
            now = datetime.now().isoformat()
            cur.execute(
                f"""
                UPDATE balances
                SET balance = CASE WHEN balance > {p} THEN balance - {p} ELSE 0 END,
                    updated_at = {p}
                """,
                (int(amount), int(amount), now)
            )
            changed = cur.rowcount
            conn.commit()
            cur.close()
            conn.close()
            return changed
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            print(f"?? Erro ao remover saldo de todos: {e}")
            return 0


def reset_all_balances() -> int:
    init_db()
    with DB_LOCK:
        conn = None
        try:
            conn = _connect_db()
            cur = conn.cursor()
            now = datetime.now().isoformat()
            p = _db_placeholder()
            cur.execute(f"UPDATE balances SET balance = 0, updated_at = {p}", (now,))
            changed = cur.rowcount
            conn.commit()
            cur.close()
            conn.close()
            return changed
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            print(f"?? Erro ao resetar saldos: {e}")
            return 0


def claim_starter_balance(user_id: int, amount: int, cooldown_days: int = 365):
    init_db()
    if amount <= 0:
        return False, None, get_balance(user_id)

    with DB_LOCK:
        conn = None
        try:
            conn = _connect_db()
            cur = conn.cursor()
            p = _db_placeholder()
            uid = str(user_id)
            now = datetime.now()
            now_text = now.isoformat()
            cooldown = timedelta(days=cooldown_days)

            cur.execute(f"SELECT claimed_at FROM starter_claims WHERE user_id = {p}", (uid,))
            row = cur.fetchone()
            if row:
                try:
                    last_claim = datetime.fromisoformat(str(row[0]))
                except ValueError:
                    last_claim = now

                elapsed = now - last_claim
                if elapsed < cooldown:
                    cur.close()
                    conn.close()
                    return False, cooldown - elapsed, get_balance(user_id)

                cur.execute(f"UPDATE starter_claims SET claimed_at = {p} WHERE user_id = {p}", (now_text, uid))
            else:
                cur.execute(f"INSERT INTO starter_claims (user_id, claimed_at) VALUES ({p}, {p})", (uid, now_text))

            cur.execute(
                f"""
                INSERT INTO balances (user_id, balance, updated_at)
                VALUES ({p}, {p}, {p})
                ON CONFLICT(user_id) DO UPDATE SET
                    balance = balances.balance + excluded.balance,
                    updated_at = excluded.updated_at
                """,
                (uid, int(amount), now_text)
            )
            conn.commit()
            cur.close()
            conn.close()
            return True, None, get_balance(user_id)
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            print(f"?? Erro ao resgatar saldo inicial de {user_id}: {e}")
            return False, None, get_balance(user_id)
def load_starter_claims():
    init_db()
    with DB_LOCK:
        try:
            conn = _connect_db()
            cur = conn.cursor()
            cur.execute("SELECT user_id, claimed_at FROM starter_claims")
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return {str(user_id): str(claimed_at) for user_id, claimed_at in rows}
        except Exception as e:
            print(f"⚠️ Erro ao carregar starter_claims do banco: {e}")
            return {}


def save_starter_claims(data):
    init_db()
    if data is None:
        return False

    with DB_LOCK:
        try:
            conn = _connect_db()
            cur = conn.cursor()
            p = _db_placeholder()
            for user_id, claimed_at in data.items():
                cur.execute(
                    f"""
                    INSERT INTO starter_claims (user_id, claimed_at)
                    VALUES ({p}, {p})
                    ON CONFLICT(user_id) DO UPDATE SET claimed_at = excluded.claimed_at
                    """,
                    (str(user_id), str(claimed_at))
                )
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            print(f"⚠️ Erro ao salvar starter_claims no banco: {e}")
            return False


def load_orders():
    init_db()
    with DB_LOCK:
        try:
            conn = _connect_db()
            cur = conn.cursor()
            cur.execute("SELECT order_id, data FROM orders")
            rows = cur.fetchall()
            cur.close()
            conn.close()

            result = {}
            for order_id, raw_data in rows:
                try:
                    result[str(order_id)] = json.loads(raw_data)
                except Exception:
                    pass
            return result
        except Exception as e:
            print(f"⚠️ Erro ao carregar pedidos do banco: {e}")
            return {}


def save_orders(data):
    init_db()
    if data is None:
        return False

    with DB_LOCK:
        try:
            conn = _connect_db()
            cur = conn.cursor()
            p = _db_placeholder()

            for order_id, order in data.items():
                if not isinstance(order, dict):
                    continue
                cur.execute(
                    f"""
                    INSERT INTO orders (order_id, user_id, status, created_at, data)
                    VALUES ({p}, {p}, {p}, {p}, {p})
                    ON CONFLICT(order_id) DO UPDATE SET
                        user_id = excluded.user_id,
                        status = excluded.status,
                        created_at = excluded.created_at,
                        data = excluded.data
                    """,
                    (
                        str(order_id),
                        str(order.get("user_id", "")),
                        str(order.get("status", "")),
                        str(order.get("created_at", datetime.now().isoformat())),
                        json.dumps(order, ensure_ascii=False)
                    )
                )

            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            print(f"⚠️ Erro ao salvar pedidos no banco: {e}")
            return False


# =========================
# ITENS DA LOJA
# =========================
SHOP_CATEGORIES = {
    "🧱 Construção & Kits de Base": {
        1: {"name": "Caixa de Pregos", "czp": 400},
        2: {"name": "Pacote de Tábuas (30)", "czp": 550},
        3: {"name": "Serrote", "czp": 200},
        4: {"name": "CodeLock", "czp": 900},
        5: {"name": "Bandeira", "czp": 600},
        7: {"name": "Chapa de Metal (10)", "czp": 2200},
        8: {"name": "Bica de Água", "czp": 2600},
        9: {"name": "Arame Farpado", "czp": 500},
    },

    "📦 Armazenamento": {
        13: {"name": "Container Pequeno", "czp": 500},
        14: {"name": "Container Médio", "czp": 900},
        15: {"name": "Armário Militar Grande", "czp": 1600}
    },

    "🏎️ Veículos Mod": {
        16: {"name": "Mod Car 4x4", "czp": 3800},
        17: {"name": "Mod Car Sedan", "czp": 3800}
    },

    "🔧 Peças & Utilitários de Carro": {
        18: {"name": "Chave de Carro", "czp": 1275},
        19: {"name": "Lock Pick de Carro", "czp": 2575},
        20: {"name": "Bateria de Carro", "czp": 500},
        21: {"name": "Radiador de Carro", "czp": 500},
        22: {"name": "Vela de Ignição de Carro", "czp": 400},
        23: {"name": "Roda de Carro", "czp": 600},
        24: {"name": "Galão de Gasolina", "czp": 500}
    },

    "🎒 Equipamentos & Sobrevivência": {
        25: {"name": "Machadinha", "czp": 300},
        26: {"name": "Pedra de Amolar", "czp": 350},
        27: {"name": "Kit Inicial", "czp": 750},
        28: {"name": "Mochila MMG 120", "czp": 1600},
        29: {"name": "Kit NBC Completo", "czp": 1800},
        30: {"name": "Massa Epóxi", "czp": 400},
        31: {"name": "Nightvision", "czp": 2600}
    },

}

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
        "price_brl": "R$ 10,00",
        "czp": 500,
        "bonus": "Pacote inicial"
    },
    "p2": {
        "name": "Survivor Pack",
        "price_brl": "R$ 20,00",
        "czp": 1100,
        "bonus": "Pacote sobrevivente"
    },
    "p3": {
        "name": "Raider Pack",
        "price_brl": "R$ 50,00",
        "czp": 3000,
        "bonus": "Pacote raider"
    },
    "p4": {
        "name": "Warlord Pack",
        "price_brl": "R$ 100,00",
        "czp": 6200,
        "bonus": "Pacote avançado"
    },
    "p5": {
        "name": "Black Market Pack",
        "price_brl": "R$ 200,00",
        "czp": 14000,
        "bonus": "Pacote black market"
    },
    "p6": {
        "name": "Carnage Elite Pack",
        "price_brl": "R$ 450,00",
        "czp": 38000,
        "bonus": "Pacote elite"
    }
}


# =========================
# TRADUÇÃO ESPANHOL
# =========================
CATEGORY_ES = {
    "🧱 Construção & Kits de Base": "🧱 Construcción y Kits de Base",
    "📦 Armazenamento": "📦 Almacenamiento",
    "🏎️ Veículos Mod": "🏎️ Vehículos Mod",
    "🔧 Peças & Utilitários de Carro": "🔧 Piezas y Utilidades de Auto",
    "🎒 Equipamentos & Sobrevivência": "🎒 Equipamiento y Supervivencia"
}

ITEM_ES = {
    "Caixa de Pregos": "Caja de Clavos",
    "Pacote de Tábuas (30)": "Paquete de Tablas (30)",
    "Serrote": "Serrucho",
    "CodeLock": "CodeLock",
    "Bandeira": "Bandera",
    "Chapa de Metal (10)": "Chapa de Metal (10)",
    "Bica de Água": "Tanque de Agua",
    "Arame Farpado": "Alambre de Púas",
    "Container Pequeno": "Contenedor Pequeño",
    "Container Médio": "Contenedor Mediano",
    "Armário Militar Grande": "Armario Militar Grande",
    "Mod Car 4x4": "Auto Mod 4x4",
    "Mod Car Sedan": "Auto Mod Sedán",
    "Chave de Carro": "Llave de Auto",
    "Lock Pick de Carro": "Ganzúa de Auto",
    "Bateria de Carro": "Batería de Auto",
    "Radiador de Carro": "Radiador de Auto",
    "Vela de Ignição de Carro": "Bujía de Auto",
    "Roda de Carro": "Rueda de Auto",
    "Galão de Gasolina": "Bidón de Gasolina",
    "Machadinha": "Hacha Pequeña",
    "Pedra de Amolar": "Piedra de Afilar",
    "Kit Inicial": "Kit Inicial",
    "Mochila MMG 120": "Mochila MMG 120",
    "Kit NBC Completo": "Kit NBC Completo",
    "Massa Epóxi": "Masilla Epoxi",
    "Nightvision": "Visión Nocturna"
}

PACKAGE_ES = {
    "Grátis - Saldo Inicial": "Gratis - Saldo Inicial",
    "Starter Pack": "Paquete Inicial",
    "Survivor Pack": "Paquete Sobreviviente",
    "Raider Pack": "Paquete Raider",
    "Warlord Pack": "Paquete Warlord",
    "Black Market Pack": "Paquete Mercado Negro",
    "Carnage Elite Pack": "Paquete Carnage Elite",
    "Standard Rate": "Tarifa Estándar",
    "5% Bonus Included": "5% de Bono Incluido",
    "10% Bonus Included": "10% de Bono Incluido",
    "20% Bonus (Best Value)": "20% de Bono (Mejor Oferta)",
    "Disponível a cada 365 dias": "Disponible cada 365 días",
    "Pacote inicial": "Paquete inicial",
    "Pacote sobrevivente": "Paquete sobreviviente",
    "Pacote raider": "Paquete raider",
    "Pacote avançado": "Paquete avanzado",
    "Taxa padrão": "Tarifa estándar",
    "5% de bônus incluso": "5% de bono incluido",
    "10% de bônus incluso": "10% de bono incluido",
    "20% de bônus - Melhor custo benefício": "20% de bono - Mejor costo-beneficio",
    "+775 CZP bônus": "+775 CZP bono",
    "+2150 CZP bônus": "+2150 CZP bono",
    "Pacote black market": "Paquete mercado negro",
    "Pacote elite": "Paquete elite"
}


def es_item_name(name: str) -> str:
    return ITEM_ES.get(name, name)


def es_category_name(name: str) -> str:
    return CATEGORY_ES.get(name, name)


def es_package_text(text: str) -> str:
    return PACKAGE_ES.get(text, text)


# =========================
# FUNÇÕES AUXILIARES
# =========================
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
        title="🏪 CARNAGE Z - MERCADO CZP",
        description=(
            "Bem-vindo ao mercado oficial do servidor! 🛍️\n"
            "Use os botões interativos abaixo para realizar suas compras ou consultar dados.\n\n"
            "**━━━━━━━━━━━━━━━━━━━━━━━━━━**"
        ),
        color=0x00FF88
    )

    for category_name, items in SHOP_CATEGORIES.items():
        value = ""
        for item_id, item in items.items():
            value += f"`ID {str(item_id).zfill(2)}` 🔹 **{item['name']}** ➔ `{item['czp']} CZP`\n"

        embed.add_field(
            name=f"\n{category_name}",
            value=value + "**━━━━━━━━━━━━━━━━━━━━━━━━━━**",
            inline=False
        )

    embed.set_footer(text="Carnage Z Store System • Desenvolvido com carinho")
    return embed


def build_czp_packages_embed():
    embed = discord.Embed(
        title="💳 ADQUIRIR MOEDAS CZP",
        description=(
            "Fortaleça sua jornada e ajude a manter o servidor online!\n"
            "Escolha um dos pacotes abaixo utilizando o menu de seleção.\n\n"
            "**━━━━━━━━━━━━━━━━━━━━━━━━━━**"
        ),
        color=0xFFD700
    )

    paid_value = (
        "💵 **R$ 10,00** ➔ `500 CZP` │ *Starter Pack*\n"
        "💵 **R$ 20,00** ➔ `1100 CZP` │ *Survivor Pack*\n"
        "💵 **R$ 50,00** ➔ `3000 CZP` │ *Raider Pack*\n"
        "💵 **R$ 100,00** ➔ `6200 CZP` │ *Warlord Pack*\n"
        "💵 **R$ 200,00** ➔ `14.000 CZP` │ *Black Market Pack*\n"
        "💵 **R$ 450,00** ➔ `38.000 CZP` │ *Carnage Elite Pack*"
    )

    embed.add_field(
        name="💰 Pacotes Disponíveis (PIX)",
        value=paid_value,
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
class CategorySelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=category_name,
                description=f"Ver itens de {category_name.split(' ')[-1]}",
                value=category_name
            )
            for category_name in SHOP_CATEGORIES.keys()
        ]

        super().__init__(
            placeholder="Selecione uma categoria primeiro...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_category = self.values[0]

        await interaction.response.send_message(
            f"📂 Categoria selecionada: **{selected_category}**\nEscolha o item abaixo para concluir o resgate/compra:",
            view=ItemSelectView(selected_category),
            ephemeral=True
        )


class CategorySelectView(ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(CategorySelect())


class ItemSelect(ui.Select):
    def __init__(self, category_name: str):
        self.category_name = category_name
        items = SHOP_CATEGORIES[category_name]

        options = [
            discord.SelectOption(
                label=f"ID {str(item_id).zfill(2)} - {item['name']}",
                description=f"Custo: {item['czp']} CZP",
                value=str(item_id)
            )
            for item_id, item in items.items()
        ]

        super().__init__(
            placeholder="Selecione o item desejado...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_item_id = int(self.values[0])
        await interaction.response.send_modal(PurchaseModal(selected_item_id))


class ItemSelectView(ui.View):
    def __init__(self, category_name: str):
        super().__init__(timeout=120)
        self.add_item(ItemSelect(category_name))


class BuySelectView(ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(CategorySelect())


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
                label="R$ 10,00 • 500 CZP",
                description="Starter Pack",
                value="p1"
            ),
            discord.SelectOption(
                label="R$ 20,00 • 1100 CZP",
                description="Survivor Pack",
                value="p2"
            ),
            discord.SelectOption(
                label="R$ 50,00 • 3000 CZP",
                description="Raider Pack",
                value="p3"
            ),
            discord.SelectOption(
                label="R$ 100,00 • 6200 CZP",
                description="Warlord Pack",
                value="p4"
            ),
            discord.SelectOption(
                label="R$ 200,00 • 14.000 CZP",
                description="Black Market Pack",
                value="p5"
            ),
            discord.SelectOption(
                label="R$ 450,00 • 38.000 CZP",
                description="Carnage Elite Pack",
                value="p6"
            ),
        ]

        super().__init__(
            placeholder="Selecione um pacote de CZP...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_package_id = self.values[0]
        package = CZP_PACKAGES[selected_package_id]

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

            claimed, remaining, new_balance = claim_starter_balance(interaction.user.id, package["czp"])
            if not claimed:
                if remaining:
                    days = remaining.days
                    hours = remaining.seconds // 3600
                    await interaction.response.send_message(
                        f"Voce ja resgatou seu saldo inicial.\n"
                        f"Tente novamente em **{days} dias e {hours} horas**.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message("Nao consegui liberar o saldo inicial agora.", ephemeral=True)
                return

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
                f"💵 **Valor:** {package['price_brl']}\n"
                f"💰 **CZP:** {package['czp']} CZP\n"
                f"✨ **Detalhe:** {package['bonus']}\n\n"
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
# EMBEDS E VIEWS EM ESPANHOL
# =========================
def build_shop_embed_es():
    embed = discord.Embed(
        title="🏪 CARNAGE Z - MERCADO CZP",
        description=(
            "¡Bienvenido al mercado oficial del servidor! 🛍️\n"
            "Usa los botones interactivos de abajo para comprar o consultar datos.\n\n"
            "**━━━━━━━━━━━━━━━━━━━━━━━━━━**"
        ),
        color=0x00FF88
    )

    for category_name, items in SHOP_CATEGORIES.items():
        value = ""
        for item_id, item in items.items():
            value += f"`ID {str(item_id).zfill(2)}` 🔹 **{es_item_name(item['name'])}** ➔ `{item['czp']} CZP`\n"

        embed.add_field(
            name=f"\n{es_category_name(category_name)}",
            value=value + "**━━━━━━━━━━━━━━━━━━━━━━━━━━**",
            inline=False
        )

    embed.set_footer(text="Sistema de Tienda Carnage Z • Desarrollado con cariño")
    return embed


def build_czp_packages_embed_es():
    embed = discord.Embed(
        title="💳 ADQUIRIR MONEDAS CZP",
        description=(
            "¡Fortalece tu aventura y ayuda a mantener el servidor online!\n"
            "Elige uno de los paquetes usando el menú de selección.\n\n"
            "**━━━━━━━━━━━━━━━━━━━━━━━━━━**"
        ),
        color=0xFFD700
    )

    paid_value = (
        "💵 **R$ 10,00** ➔ `500 CZP` │ *Paquete Inicial*\n"
        "💵 **R$ 20,00** ➔ `1100 CZP` │ *Paquete Sobreviviente*\n"
        "💵 **R$ 50,00** ➔ `3000 CZP` │ *Paquete Raider*\n"
        "💵 **R$ 100,00** ➔ `6200 CZP` │ *Paquete Warlord*\n"
        "💵 **R$ 200,00** ➔ `14.000 CZP` │ *Paquete Mercado Negro*\n"
        "💵 **R$ 450,00** ➔ `38.000 CZP` │ *Paquete Carnage Elite*"
    )

    embed.add_field(
        name="💰 Paquetes Disponibles (PIX)",
        value=paid_value,
        inline=False
    )

    embed.set_footer(text="Carnage Z CZP Store")
    return embed


class PurchaseModalES(ui.Modal, title="Finalizar Compra"):
    def __init__(self, selected_item_id: int):
        super().__init__()
        self.selected_item_id = selected_item_id

        self.nickname = ui.TextInput(
            label="Nickname en el juego",
            placeholder="Escribe tu nickname en el servidor",
            min_length=2,
            max_length=32
        )

        self.item_id_input = ui.TextInput(
            label="ID del Ítem",
            placeholder=f"Confirma el ID del ítem ({selected_item_id})",
            min_length=1,
            max_length=3
        )

        self.quantity = ui.TextInput(
            label="Cantidad",
            placeholder="Ej: 1",
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
            await interaction.followup.send("❌ El ID del ítem y la cantidad deben ser números.", ephemeral=True)
            return

        if quantity <= 0:
            await interaction.followup.send("❌ La cantidad debe ser mayor que 0.", ephemeral=True)
            return

        if typed_item_id != self.selected_item_id:
            await interaction.followup.send(
                f"❌ El ID escrito no corresponde al ítem elegido. Seleccionaste el ítem **{self.selected_item_id}**.",
                ephemeral=True
            )
            return

        item = SHOP_ITEMS.get(typed_item_id)
        if not item:
            await interaction.followup.send("❌ Ítem inválido.", ephemeral=True)
            return

        total_price = item["czp"] * quantity
        current_balance = get_balance(interaction.user.id)

        if current_balance < total_price:
            await interaction.followup.send(
                f"❌ Saldo insuficiente.\n"
                f"Tu saldo actual: **{current_balance} CZP**\n"
                f"Total de la compra: **{total_price} CZP**",
                ephemeral=True
            )
            return

        success = remove_balance(interaction.user.id, total_price)
        if not success:
            await interaction.followup.send("❌ No fue posible descontar el saldo. Inténtalo de nuevo.", ephemeral=True)
            return

        new_balance = get_balance(interaction.user.id)
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        buyer_embed = discord.Embed(
            title="🧾 Recibo de Compra - CZP Store",
            color=0x00FF88,
            timestamp=datetime.now()
        )
        buyer_embed.add_field(name="Comprador", value=interaction.user.mention, inline=False)
        buyer_embed.add_field(name="Nickname en el juego", value=self.nickname.value, inline=False)
        buyer_embed.add_field(name="Ítem", value=es_item_name(item["name"]), inline=False)
        buyer_embed.add_field(name="ID del Ítem", value=str(typed_item_id), inline=True)
        buyer_embed.add_field(name="Cantidad", value=str(quantity), inline=True)
        buyer_embed.add_field(name="Total", value=f"{total_price} CZP", inline=True)
        buyer_embed.add_field(name="Saldo restante", value=f"{new_balance} CZP", inline=False)
        buyer_embed.set_footer(text=f"Pedido realizado el {timestamp}")

        dm_sent = await send_dm_safe(interaction.user, buyer_embed)

        admin_embed = discord.Embed(
            title="📦 Nuevo Pedido VIP",
            color=0xFFD700,
            timestamp=datetime.now()
        )
        admin_embed.add_field(name="Usuario", value=f"{interaction.user} ({interaction.user.id})", inline=False)
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
            f"✅ Compra registrada con éxito.\n"
            f"Ítem: **{es_item_name(item['name'])}**\n"
            f"Cantidad: **{quantity}**\n"
            f"Total: **{total_price} CZP**\n"
            f"Saldo restante: **{new_balance} CZP**"
        )

        if dm_sent:
            msg += "\n📩 Se envió un recibo a tu DM."
        else:
            msg += "\n⚠️ No pude enviar DM. Verifica si tus mensajes privados están abiertos."

        await interaction.followup.send(msg, ephemeral=True)


class CategorySelectES(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=es_category_name(category_name),
                description=f"Ver ítems de {es_category_name(category_name)}",
                value=category_name
            )
            for category_name in SHOP_CATEGORIES.keys()
        ]

        super().__init__(
            placeholder="Selecciona una categoría primero...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_category = self.values[0]

        await interaction.response.send_message(
            f"📂 Categoría seleccionada: **{es_category_name(selected_category)}**\nElige el ítem de abajo para finalizar el canje/compra:",
            view=ItemSelectViewES(selected_category),
            ephemeral=True
        )


class ItemSelectES(ui.Select):
    def __init__(self, category_name: str):
        items = SHOP_CATEGORIES[category_name]

        options = [
            discord.SelectOption(
                label=f"ID {str(item_id).zfill(2)} - {es_item_name(item['name'])}",
                description=f"Costo: {item['czp']} CZP",
                value=str(item_id)
            )
            for item_id, item in items.items()
        ]

        super().__init__(
            placeholder="Selecciona el ítem deseado...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_item_id = int(self.values[0])
        await interaction.response.send_modal(PurchaseModalES(selected_item_id))


class ItemSelectViewES(ui.View):
    def __init__(self, category_name: str):
        super().__init__(timeout=120)
        self.add_item(ItemSelectES(category_name))


class BuySelectViewES(ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(CategorySelectES())


class CZPPackageSelectES(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="R$ 10,00 • 500 CZP", description="Paquete Inicial", value="p1"),
            discord.SelectOption(label="R$ 20,00 • 1100 CZP", description="Paquete Sobreviviente", value="p2"),
            discord.SelectOption(label="R$ 50,00 • 3000 CZP", description="Paquete Raider", value="p3"),
            discord.SelectOption(label="R$ 100,00 • 6200 CZP", description="Paquete Warlord", value="p4"),
            discord.SelectOption(label="R$ 200,00 • 14.000 CZP", description="Mercado Negro", value="p5"),
            discord.SelectOption(label="R$ 450,00 • 38.000 CZP", description="Carnage Elite", value="p6"),
        ]

        super().__init__(placeholder="Selecciona un paquete de CZP...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_package_id = self.values[0]
        package = CZP_PACKAGES[selected_package_id]

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
                        f"❌ Ya canjeaste tu saldo inicial.\nInténtalo de nuevo en **{days} días y {hours} horas**.",
                        ephemeral=True
                    )
                    return

            claimed, remaining, new_balance = claim_starter_balance(interaction.user.id, package["czp"])
            if not claimed:
                if remaining:
                    days = remaining.days
                    hours = remaining.seconds // 3600
                    await interaction.response.send_message(
                        f"Ya canjeaste tu saldo inicial.\n"
                        f"Intentalo de nuevo en **{days} dias y {hours} horas**.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message("No pude liberar el saldo inicial ahora.", ephemeral=True)
                return

            free_embed = discord.Embed(
                title="🎁 Recibo de Canje CZP",
                description="Tu saldo inicial fue liberado con éxito.",
                color=0x2ECC71,
                timestamp=datetime.now()
            )
            free_embed.add_field(name="Paquete", value=f"{es_package_text(package['name'])} - {package['czp']} CZP", inline=False)
            free_embed.add_field(name="Saldo actual", value=f"{new_balance} CZP", inline=False)
            free_embed.set_footer(text="Carnage Z CZP")
            await send_dm_safe(interaction.user, free_embed)

            admin_embed = discord.Embed(title="🎁 Resgate de CZP Grátis", color=0x2ECC71, timestamp=datetime.now())
            admin_embed.add_field(name="Usuário", value=f"{interaction.user} ({interaction.user.id})", inline=False)
            admin_embed.add_field(name="Pacote", value=f"{package['name']} - {package['czp']} CZP", inline=False)
            admin_embed.add_field(name="Novo saldo", value=f"{new_balance} CZP", inline=False)
            admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
            if admin_channel:
                await admin_channel.send(embed=admin_embed)

            await interaction.response.send_message(
                f"✅ Recibiste **{package['czp']} CZP** gratis.\nTu nuevo saldo es **{new_balance} CZP**.",
                ephemeral=True
            )
            return

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
            title="💳 Pago por PIX - CZP",
            description=(
                f"**Pedido:** `{order_id}`\n\n"
                f"Seleccionaste el paquete **{es_package_text(package['name'])}**.\n\n"
                f"💵 **Valor:** {package['price_brl']}\n"
                f"💰 **CZP:** {package['czp']} CZP\n"
                f"✨ **Detalle:** {es_package_text(package['bonus'])}\n\n"
                f"Haz el pago por PIX usando el QR Code o copia el código de abajo."
            ),
            color=0x00C853,
            timestamp=datetime.now()
        )
        payment_embed.add_field(name="📋 Código PIX Copia y Pega", value=f"```{PIX_CODE}```", inline=False)
        payment_embed.add_field(
            name="🧾 Instrucciones",
            value=(
                "1. Haz el pago del valor exacto\n"
                "2. Guarda el comprobante\n"
                "3. Envía el comprobante al equipo/admin por ticket\n"
                "4. Después de la confirmación, tu saldo CZP será agregado"
            ),
            inline=False
        )
        payment_embed.set_footer(text="Carnage Z • Pago CZP")
        dm_sent = await send_dm_with_pix(interaction.user, payment_embed)

        admin_embed = discord.Embed(title="💳 Novo Pedido de CZP", description="Pedido aguardando pagamento/confirmação.", color=0xFFD700, timestamp=datetime.now())
        admin_embed.add_field(name="Pedido", value=order_id, inline=False)
        admin_embed.add_field(name="Usuário", value=f"{interaction.user} ({interaction.user.id})", inline=False)
        admin_embed.add_field(name="Pacote", value=package["name"], inline=False)
        admin_embed.add_field(name="Valor", value=package["price_brl"], inline=True)
        admin_embed.add_field(name="CZP", value=f"{package['czp']} CZP", inline=True)
        admin_embed.add_field(name="Observação", value=package["bonus"], inline=False)
        admin_embed.add_field(name="Status", value="Aguardando pagamento", inline=False)
        admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
        if admin_channel:
            await admin_channel.send(embed=admin_embed, view=AdminCZPOrderView(order_id))

        user_msg = (
            f"✅ Tu pedido fue creado con éxito.\n"
            f"**Paquete:** {es_package_text(package['name'])}\n"
            f"**Valor:** {package['price_brl']}\n"
            f"**CZP:** {package['czp']} CZP\n\n"
        )
        if dm_sent:
            user_msg += "📩 Te envié el QR Code y el código PIX por DM."
        else:
            user_msg += "⚠️ No pude enviar DM.\nAbre tu DM e inténtalo de nuevo, o habla con el equipo."

        await interaction.response.send_message(user_msg, ephemeral=True)


class CZPPackageViewES(ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(CZPPackageSelectES())


class SpanishShopView(ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @ui.button(label="🛒 Comprar Ítems", style=discord.ButtonStyle.success)
    async def buy_button_es(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            "Selecciona primero la categoría del ítem:",
            view=BuySelectViewES(),
            ephemeral=True
        )

    @ui.button(label="💰 Ver Mi Saldo", style=discord.ButtonStyle.primary)
    async def balance_button_es(self, interaction: discord.Interaction, button: ui.Button):
        balance = get_balance(interaction.user.id)
        balance_embed = discord.Embed(
            title="💰 Saldo CZP",
            description=f"Tu saldo actual es **{balance} CZP**",
            color=0x3498DB,
            timestamp=datetime.now()
        )
        balance_embed.set_footer(text="Carnage Z Coins")
        dm_sent = await send_dm_safe(interaction.user, balance_embed)

        if dm_sent:
            await interaction.response.send_message("📩 Envié tu saldo por DM.", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ No pude enviarte DM.\nTu saldo actual es **{balance} CZP**", ephemeral=True)

    @ui.button(label="💳 Adquirir Monedas CZP", style=discord.ButtonStyle.primary)
    async def acquire_czp_button_es(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(embed=build_czp_packages_embed_es(), view=CZPPackageViewES(), ephemeral=True)

# =========================
# BOTÕES PRINCIPAIS
# =========================
class MainShopView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🛒 Comprar Itens", style=discord.ButtonStyle.success, custom_id="czp_buy_button")
    async def buy_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            "Selecione primeiro a categoria do item:",
            view=BuySelectView(),
            ephemeral=True
        )

    @ui.button(label="💰 Ver Meu Saldo", style=discord.ButtonStyle.primary, custom_id="czp_balance_button")
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

    @ui.button(label="💳 Adquirir Moedas CZP", style=discord.ButtonStyle.primary, custom_id="czp_acquire_button")
    async def acquire_czp_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            embed=build_czp_packages_embed(),
            view=CZPPackageView(),
            ephemeral=True
        )

    @ui.button(label="🇪🇸 Español", style=discord.ButtonStyle.secondary, custom_id="czp_spanish_button")
    async def spanish_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            embed=build_shop_embed_es(),
            view=SpanishShopView(),
            ephemeral=True
        )


# =========================
# EVENTOS
# =========================
@bot.event
async def on_ready():
    init_db()
    bot.add_view(MainShopView())
    print(f"✅ Bot online como {bot.user}")


# =========================
# COMANDO ADMIN PARA POSTAR A LOJA
# =========================
@bot.command()
@commands.has_permissions(administrator=True)
async def setup_shop(ctx):
    async for message in ctx.channel.history(limit=50):
        if message.author == bot.user and message.embeds:
            if message.embeds[0].title == "🏪 CARNAGE Z - MERCADO CZP":
                await message.delete()

    embed = build_shop_embed()
    await ctx.send(embed=embed, view=MainShopView())


# =========================
# COMANDOS ADMIN DE MOEDAS
# =========================
@bot.command()
@commands.has_permissions(administrator=True)
async def addcoins(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        await ctx.send("O valor precisa ser maior que 0.")
        return

    if not add_balance(member.id, amount):
        await ctx.send("Erro ao acessar o banco de saldos. Comando cancelado.")
        return

    new_balance = get_balance(member.id)
    await ctx.send(f"{amount} CZP adicionados para {member.mention}. Saldo atual: **{new_balance} CZP**")


@bot.command()
@commands.has_permissions(administrator=True)
async def setcoins(ctx, member: discord.Member, amount: int):
    if amount < 0:
        await ctx.send("O valor nao pode ser negativo.")
        return

    if not set_balance(member.id, amount):
        await ctx.send("Erro ao acessar o banco de saldos. Comando cancelado.")
        return

    await ctx.send(f"Saldo de {member.mention} definido para **{amount} CZP**")


@bot.command()
@commands.has_permissions(administrator=True)
async def saldo(ctx, member: discord.Member = None):
    member = member or ctx.author
    balance = get_balance(member.id)
    await ctx.send(f"Saldo de {member.mention}: **{balance} CZP**")


@bot.command()
@commands.has_permissions(administrator=True)
async def addall(ctx, amount: int):
    if amount <= 0:
        await ctx.send("O valor precisa ser maior que 0.")
        return

    changed = add_balance_all(amount)
    if changed <= 0:
        await ctx.send("Nenhum usuario encontrado no banco de dados.")
        return

    await ctx.send(f"{amount} CZP adicionados para TODOS os usuarios cadastrados.")


@bot.command()
@commands.has_permissions(administrator=True)
async def removeall(ctx, amount: int):
    if amount <= 0:
        await ctx.send("O valor precisa ser maior que 0.")
        return

    changed = remove_balance_all(amount)
    if changed <= 0:
        await ctx.send("Nenhum usuario encontrado no banco de dados.")
        return

    await ctx.send(f"{amount} CZP removidos de TODOS os usuarios cadastrados.")


@bot.command()
@commands.has_permissions(administrator=True)
async def resetall(ctx):
    changed = reset_all_balances()
    if changed <= 0:
        await ctx.send("Nenhum usuario para resetar.")
        return

    await ctx.send("Todos os saldos foram resetados para 0.")


@bot.command()
@commands.has_permissions(administrator=True)
async def removecoins(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        await ctx.send("O valor precisa ser maior que 0.")
        return

    current_balance = get_balance(member.id)
    if current_balance <= 0:
        await ctx.send(f"{member.mention} nao tem CZP para remover.")
        return

    removed_amount = min(amount, current_balance)
    if not remove_balance(member.id, removed_amount):
        await ctx.send("Erro ao acessar o banco de saldos. Comando cancelado.")
        return

    new_balance = get_balance(member.id)
    await ctx.send(
        f"{removed_amount} CZP removidos de {member.mention}. "
        f"Saldo atual: **{new_balance} CZP**"
    )

@bot.command()
@commands.has_permissions(administrator=True)
async def confirmczp(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        await ctx.send("❌ O valor precisa ser maior que 0.")
        return

    success = add_balance(member.id, amount)
    if not success:
        await ctx.send("❌ Erro ao acessar o arquivo de saldos. Comando cancelado.")
        return
        
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
    if data is None:
        await ctx.send("❌ Erro ao carregar os dados do Leaderboard.")
        return

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
