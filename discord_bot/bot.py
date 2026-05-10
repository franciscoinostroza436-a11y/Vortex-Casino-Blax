import discord
from discord import app_commands
import aiosqlite
import asyncio
import random
import os
from datetime import datetime, timedelta

TOKEN = os.environ.get("DISCORD_TOKEN")
DB_PATH = "discord_bot/casino.db"

SHOP_ITEMS = {
    "anti_rob": {
        "name": "🛡️ Escudo Anti-Robo",
        "price": 800,
        "description": "Bloquea automáticamente el próximo intento de robo. ¡Consumible!",
        "category": "proteccion",
    },
    "vip_card": {
        "name": "🎩 Tarjeta VIP",
        "price": 2000,
        "description": "Acceso VIP al casino. Decorativo.",
        "category": "decorativo",
    },
    "lucky_charm": {
        "name": "🍀 Amuleto de la Suerte",
        "price": 1000,
        "description": "Un amuleto que trae buena fortuna. Decorativo.",
        "category": "decorativo",
    },
    "golden_chip": {
        "name": "🪙 Ficha Dorada",
        "price": 5000,
        "description": "La ficha más exclusiva del casino. Decorativo.",
        "category": "decorativo",
    },
    "cocktail": {
        "name": "🍹 Cóctel de Casino",
        "price": 300,
        "description": "Una bebida elegante para el jugador. Decorativo.",
        "category": "decorativo",
    },
    "sunglasses": {
        "name": "🕶️ Gafas de Poker",
        "price": 750,
        "description": "Para que nadie lea tu cara. Decorativo.",
        "category": "decorativo",
    },
    "role_vip": {
        "name": "🎩 Rol: Casino VIP",
        "price": 3000,
        "description": "Gana **+300** 🪙 cada 12h con `/collect`.",
        "category": "rol",
        "collect_bonus": 300,
        "collect_hours": 12,
    },
    "role_viciado": {
        "name": "🎮 Rol: Viciado Casino",
        "price": 7000,
        "description": "Gana **+700** 🪙 cada 8h con `/collect`.",
        "category": "rol",
        "collect_bonus": 700,
        "collect_hours": 8,
    },
    "role_supremo": {
        "name": "👑 Rol: Casino Supremo",
        "price": 15000,
        "description": "Gana **+1,500** 🪙 cada 6h con `/collect`.",
        "category": "rol",
        "collect_bonus": 1500,
        "collect_hours": 6,
    },
}

ROLE_ITEMS = [k for k, v in SHOP_ITEMS.items() if v["category"] == "rol"]

RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK_NUMBERS = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}

SLOTS_SYMBOLS = ["🍒", "🍋", "🍊", "🍇", "🔔", "⭐", "💎", "7️⃣"]
SLOTS_WEIGHTS = [30, 25, 20, 15, 12, 8, 5, 3]
SLOTS_PAYOUTS = {
    "7️⃣": 50,
    "💎": 20,
    "⭐": 10,
    "🔔": 5,
    "🍇": 3,
    "🍊": 3,
    "🍋": 2,
    "🍒": 2,
}

MISSIONS = {
    "play_roulette": {
        "name": "🎰 Rulero del Casino",
        "description": "Juega a la ruleta 3 veces",
        "goal": 3,
        "reward": 300,
        "action": "roulette_played",
    },
    "play_slots": {
        "name": "🎰 Fanático de Slots",
        "description": "Juega a las tragamonedas 5 veces",
        "goal": 5,
        "reward": 500,
        "action": "slots_played",
    },
    "win_blackjack": {
        "name": "🃏 As del Blackjack",
        "description": "Gana 2 partidas de blackjack",
        "goal": 2,
        "reward": 600,
        "action": "blackjack_won",
    },
    "play_crash": {
        "name": "📈 Amante del Riesgo",
        "description": "Juega al Crash 2 veces",
        "goal": 2,
        "reward": 400,
        "action": "crash_played",
    },
    "rob_success": {
        "name": "🦹 Ladrón del Casino",
        "description": "Roba exitosamente a alguien",
        "goal": 1,
        "reward": 350,
        "action": "rob_success",
    },
    "play_daily": {
        "name": "📅 Constancia",
        "description": "Usa /daily hoy",
        "goal": 1,
        "reward": 100,
        "action": "daily_used",
    },
}

USE_FLAVOR = {
    "vip_card": "✨ Muestras tu **Tarjeta VIP** en la entrada. El portero te hace una reverencia.",
    "lucky_charm": "🍀 Frotas tu **Amuleto de la Suerte**. Sientes que hoy es tu día.",
    "golden_chip": "🪙 Pones tu **Ficha Dorada** sobre la mesa. Todos en el casino guardan silencio.",
    "cocktail": "🍹 Bebes tu **Cóctel de Casino** de un sorbo. Máxima elegancia, cero monedas extra.",
    "sunglasses": "🕶️ Te pones las **Gafas de Poker**. Tu cara ahora es completamente ilegible.",
}

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 1000,
                last_daily TEXT,
                last_rob TEXT,
                last_collect TEXT
            )
        """)
        for col in ("last_rob", "last_collect"):
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
            except Exception:
                pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                item_id TEXT,
                quantity INTEGER DEFAULT 1,
                UNIQUE(user_id, item_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS missions (
                user_id TEXT,
                mission_id TEXT,
                progress INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                reset_date TEXT,
                PRIMARY KEY (user_id, mission_id)
            )
        """)
        await db.commit()


async def get_or_create_user(user_id: str, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, balance) VALUES (?, ?, 1000)",
            (user_id, username)
        )
        await db.commit()
        async with db.execute("SELECT balance, last_daily FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()


async def get_balance(user_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def update_balance(user_id: str, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()


async def get_inventory(user_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT item_id, quantity FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchall()


async def get_item_quantity(user_id: str, item_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT quantity FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, item_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def add_to_inventory(user_id: str, item_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO inventory (user_id, item_id, quantity) VALUES (?, ?, 1) "
            "ON CONFLICT(user_id, item_id) DO UPDATE SET quantity = quantity + 1",
            (user_id, item_id)
        )
        await db.commit()


async def remove_from_inventory(user_id: str, item_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE inventory SET quantity = quantity - 1 WHERE user_id = ? AND item_id = ?",
            (user_id, item_id)
        )
        await db.execute(
            "DELETE FROM inventory WHERE user_id = ? AND item_id = ? AND quantity <= 0",
            (user_id, item_id)
        )
        await db.commit()


async def get_today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


async def track_mission(user_id: str, action: str):
    today = await get_today()
    async with aiosqlite.connect(DB_PATH) as db:
        for mission_id, mission in MISSIONS.items():
            if mission["action"] != action:
                continue
            async with db.execute(
                "SELECT progress, completed, reset_date FROM missions WHERE user_id=? AND mission_id=?",
                (user_id, mission_id)
            ) as cursor:
                row = await cursor.fetchone()

            if row is None:
                await db.execute(
                    "INSERT INTO missions (user_id, mission_id, progress, completed, reset_date) VALUES (?,?,0,0,?)",
                    (user_id, mission_id, today)
                )
                progress, completed, reset_date = 0, 0, today
            else:
                progress, completed, reset_date = row

            if reset_date != today:
                progress, completed = 0, 0
                await db.execute(
                    "UPDATE missions SET progress=0, completed=0, reset_date=? WHERE user_id=? AND mission_id=?",
                    (today, user_id, mission_id)
                )

            if completed:
                continue

            new_progress = min(progress + 1, mission["goal"])
            newly_completed = 1 if new_progress >= mission["goal"] else 0
            await db.execute(
                "UPDATE missions SET progress=?, completed=?, reset_date=? WHERE user_id=? AND mission_id=?",
                (new_progress, newly_completed, today, user_id, mission_id)
            )
            if newly_completed:
                await db.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                    (mission["reward"], user_id)
                )
        await db.commit()


async def get_missions_data(user_id: str) -> list:
    today = await get_today()
    results = []
    async with aiosqlite.connect(DB_PATH) as db:
        for mission_id, mission in MISSIONS.items():
            async with db.execute(
                "SELECT progress, completed, reset_date FROM missions WHERE user_id=? AND mission_id=?",
                (user_id, mission_id)
            ) as cursor:
                row = await cursor.fetchone()

            if row is None or row[2] != today:
                progress, completed = 0, 0
            else:
                progress, completed = row[0], row[1]

            results.append({
                "id": mission_id,
                "name": mission["name"],
                "description": mission["description"],
                "goal": mission["goal"],
                "reward": mission["reward"],
                "progress": progress,
                "completed": bool(completed),
            })
    return results


@client.event
async def on_ready():
    await init_db()
    await tree.sync()
    print(f"Bot conectado como {client.user}")


@tree.command(name="balance", description="Muestra tu saldo actual")
async def balance(interaction: discord.Interaction):
    row = await get_or_create_user(str(interaction.user.id), interaction.user.name)
    embed = discord.Embed(title="💰 Tu Saldo", color=0xFFD700)
    embed.add_field(name="Monedas", value=f"**{row[0]:,}** 🪙", inline=False)
    embed.set_footer(text=f"Casino Bot • {interaction.user.name}")
    await interaction.response.send_message(embed=embed)


@tree.command(name="daily", description="Recoge tu recompensa diaria de 500 monedas")
async def daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    row = await get_or_create_user(user_id, interaction.user.name)
    last_daily = row[1]
    now = datetime.utcnow()

    if last_daily:
        last_dt = datetime.fromisoformat(last_daily)
        diff = now - last_dt
        if diff < timedelta(hours=24):
            remaining = timedelta(hours=24) - diff
            hours, remainder = divmod(int(remaining.total_seconds()), 3600)
            minutes = remainder // 60
            embed = discord.Embed(title="⏰ Recompensa No Disponible", color=0xFF4444)
            embed.description = f"Ya recogiste tu recompensa diaria.\nVuelve en **{hours}h {minutes}m**."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance + 500, last_daily = ? WHERE user_id = ?",
            (now.isoformat(), user_id)
        )
        await db.commit()

    bal = await get_balance(user_id)
    embed = discord.Embed(title="🎁 ¡Recompensa Diaria!", color=0x00FF88)
    embed.description = f"¡Recibiste **500** 🪙!\nSaldo actual: **{bal:,}** 🪙"
    await track_mission(user_id, "daily_used")
    await interaction.response.send_message(embed=embed)


@tree.command(name="collect", description="Recoge ganancias de tus roles de casino")
async def collect(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)

    owned_roles = []
    for role_id in ROLE_ITEMS:
        qty = await get_item_quantity(user_id, role_id)
        if qty > 0:
            owned_roles.append(role_id)

    if not owned_roles:
        embed = discord.Embed(title="❌ Sin Roles", color=0xFF4444)
        embed.description = (
            "No tienes ningún rol activo.\n"
            "Compra un rol en `/shop` para ganar monedas con `/collect`.\n\n"
            "🎩 **Casino VIP** — +300 🪙 cada 12h\n"
            "🎮 **Viciado Casino** — +700 🪙 cada 8h\n"
            "👑 **Casino Supremo** — +1,500 🪙 cada 6h"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    min_hours = min(SHOP_ITEMS[r]["collect_hours"] for r in owned_roles)
    total_bonus = sum(SHOP_ITEMS[r]["collect_bonus"] for r in owned_roles)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT last_collect FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            last_collect = row[0] if row else None

    now = datetime.utcnow()
    if last_collect:
        last_dt = datetime.fromisoformat(last_collect)
        diff = now - last_dt
        if diff < timedelta(hours=min_hours):
            remaining = timedelta(hours=min_hours) - diff
            hours, remainder = divmod(int(remaining.total_seconds()), 3600)
            minutes = remainder // 60
            embed = discord.Embed(title="⏰ Collect No Disponible", color=0xFF4444)
            embed.description = f"Ya recogiste tus ganancias.\nVuelve en **{hours}h {minutes}m**."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ?, last_collect = ? WHERE user_id = ?",
            (total_bonus, now.isoformat(), user_id)
        )
        await db.commit()

    new_balance = await get_balance(user_id)
    embed = discord.Embed(title="💰 ¡Ganancias Recogidas!", color=0x00FF88)
    lines = "\n".join(
        f"{SHOP_ITEMS[r]['name']} → +**{SHOP_ITEMS[r]['collect_bonus']:,}** 🪙"
        for r in owned_roles
    )
    embed.description = (
        f"{lines}\n\n"
        f"**Total:** +**{total_bonus:,}** 🪙\n"
        f"Saldo actual: **{new_balance:,}** 🪙"
    )
    await interaction.response.send_message(embed=embed)


@tree.command(name="pay", description="Transfiere monedas a otro usuario")
@app_commands.describe(usuario="El usuario que recibirá las monedas", cantidad="Cantidad a transferir")
async def pay(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    if cantidad <= 0:
        await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
        return
    if usuario.id == interaction.user.id:
        await interaction.response.send_message("❌ No puedes transferirte dinero a ti mismo.", ephemeral=True)
        return

    sender_id = str(interaction.user.id)
    receiver_id = str(usuario.id)

    await get_or_create_user(sender_id, interaction.user.name)
    await get_or_create_user(receiver_id, usuario.name)

    sender_balance = await get_balance(sender_id)
    if sender_balance < cantidad:
        embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
        embed.description = f"Tienes **{sender_balance:,}** 🪙 y quieres enviar **{cantidad:,}** 🪙."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await update_balance(sender_id, -cantidad)
    await update_balance(receiver_id, cantidad)

    embed = discord.Embed(title="💸 Transferencia Exitosa", color=0x00FF88)
    embed.description = f"**{interaction.user.mention}** le envió **{cantidad:,}** 🪙 a **{usuario.mention}**."
    await interaction.response.send_message(embed=embed)


@tree.command(name="roulette", description="Juega a la ruleta apostando por rojo o negro")
@app_commands.describe(cantidad="Cantidad a apostar", color="Elige: rojo o negro")
@app_commands.choices(color=[
    app_commands.Choice(name="🔴 Rojo", value="rojo"),
    app_commands.Choice(name="⚫ Negro", value="negro"),
])
async def roulette(interaction: discord.Interaction, cantidad: int, color: str):
    if cantidad <= 0:
        await interaction.response.send_message("❌ La apuesta debe ser mayor a 0.", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)
    bal = await get_balance(user_id)

    if bal < cantidad:
        embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
        embed.description = f"Tienes **{bal:,}** 🪙 y quieres apostar **{cantidad:,}** 🪙."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    numero = random.randint(0, 36)

    if numero == 0:
        resultado_color = "verde"
        emoji = "🟢"
    elif numero in RED_NUMBERS:
        resultado_color = "rojo"
        emoji = "🔴"
    else:
        resultado_color = "negro"
        emoji = "⚫"

    ganó = resultado_color == color

    if ganó:
        await update_balance(user_id, cantidad)
        new_balance = bal + cantidad
        embed = discord.Embed(title="🎰 ¡GANASTE!", color=0x00FF88)
        embed.description = (
            f"La ruleta cayó en **{emoji} {numero} ({resultado_color})**\n"
            f"Apostaste: **{color}** ✅\n\n"
            f"💰 Ganaste **{cantidad:,}** 🪙\n"
            f"Saldo actual: **{new_balance:,}** 🪙"
        )
    else:
        await update_balance(user_id, -cantidad)
        new_balance = bal - cantidad
        embed = discord.Embed(title="🎰 Perdiste...", color=0xFF4444)
        embed.description = (
            f"La ruleta cayó en **{emoji} {numero} ({resultado_color})**\n"
            f"Apostaste: **{color}** ❌\n\n"
            f"💸 Perdiste **{cantidad:,}** 🪙\n"
            f"Saldo actual: **{new_balance:,}** 🪙"
        )

    await track_mission(user_id, "roulette_played")
    await interaction.response.send_message(embed=embed)


@tree.command(name="slots", description="Juega a las tragamonedas")
@app_commands.describe(cantidad="Cantidad a apostar")
async def slots(interaction: discord.Interaction, cantidad: int):
    if cantidad <= 0:
        await interaction.response.send_message("❌ La apuesta debe ser mayor a 0.", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)
    bal = await get_balance(user_id)

    if bal < cantidad:
        embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
        embed.description = f"Tienes **{bal:,}** 🪙 y quieres apostar **{cantidad:,}** 🪙."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await update_balance(user_id, -cantidad)

    reels = random.choices(SLOTS_SYMBOLS, weights=SLOTS_WEIGHTS, k=3)
    display = " | ".join(reels)

    if reels[0] == reels[1] == reels[2]:
        symbol = reels[0]
        multiplier = SLOTS_PAYOUTS.get(symbol, 2)
        winnings = cantidad * multiplier
        await update_balance(user_id, winnings)
        new_balance = await get_balance(user_id)

        if symbol == "7️⃣":
            title = "🎰 ¡¡¡JACKPOT!!!"
            color = 0xFFD700
        elif symbol == "💎":
            title = "🎰 ¡GRAN PREMIO!"
            color = 0x00FFFF
        else:
            title = "🎰 ¡GANASTE!"
            color = 0x00FF88

        embed = discord.Embed(title=title, color=color)
        embed.description = (
            f"╔══════════════╗\n"
            f"║  {display}  ║\n"
            f"╚══════════════╝\n\n"
            f"¡Tres **{symbol}**! Multiplicador **x{multiplier}**\n"
            f"💰 Ganaste **{winnings:,}** 🪙\n"
            f"Saldo: **{new_balance:,}** 🪙"
        )

    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        refund = cantidad
        await update_balance(user_id, refund)
        new_balance = await get_balance(user_id)
        embed = discord.Embed(title="🎰 ¡Par!", color=0xFFAA00)
        embed.description = (
            f"╔══════════════╗\n"
            f"║  {display}  ║\n"
            f"╚══════════════╝\n\n"
            f"Dos iguales — te devolvemos la apuesta.\n"
            f"Saldo: **{new_balance:,}** 🪙"
        )

    else:
        new_balance = await get_balance(user_id)
        embed = discord.Embed(title="🎰 Sin suerte...", color=0xFF4444)
        embed.description = (
            f"╔══════════════╗\n"
            f"║  {display}  ║\n"
            f"╚══════════════╝\n\n"
            f"💸 Perdiste **{cantidad:,}** 🪙\n"
            f"Saldo: **{new_balance:,}** 🪙"
        )

    await track_mission(user_id, "slots_played")
    await interaction.response.send_message(embed=embed)


@tree.command(name="rob", description="Intenta robarle monedas a otro usuario (40% de éxito)")
@app_commands.describe(usuario="El usuario al que quieres robar")
async def rob(interaction: discord.Interaction, usuario: discord.Member):
    robber_id = str(interaction.user.id)
    victim_id = str(usuario.id)

    if usuario.id == interaction.user.id:
        await interaction.response.send_message("❌ No puedes robarte a ti mismo.", ephemeral=True)
        return
    if usuario.bot:
        await interaction.response.send_message("❌ No puedes robarle a un bot.", ephemeral=True)
        return

    await get_or_create_user(robber_id, interaction.user.name)
    await get_or_create_user(victim_id, usuario.name)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT last_rob FROM users WHERE user_id = ?", (robber_id,)) as cursor:
            row = await cursor.fetchone()
            last_rob = row[0] if row else None

    now = datetime.utcnow()
    if last_rob:
        last_dt = datetime.fromisoformat(last_rob)
        diff = now - last_dt
        if diff < timedelta(hours=1):
            remaining = timedelta(hours=1) - diff
            minutes = int(remaining.total_seconds() // 60)
            seconds = int(remaining.total_seconds() % 60)
            embed = discord.Embed(title="⏰ Cooldown Activo", color=0xFF4444)
            embed.description = f"Espera **{minutes}m {seconds}s** antes de volver a intentarlo."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

    victim_balance = await get_balance(victim_id)
    if victim_balance < 100:
        embed = discord.Embed(title="😅 Víctima Sin Fondos", color=0xFFAA00)
        embed.description = f"**{usuario.name}** tiene menos de 100 🪙. ¡No vale la pena!"
        await interaction.response.send_message(embed=embed)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_rob = ? WHERE user_id = ?", (now.isoformat(), robber_id)
        )
        await db.commit()

    anti_rob_qty = await get_item_quantity(victim_id, "anti_rob")
    if anti_rob_qty > 0:
        await remove_from_inventory(victim_id, "anti_rob")
        embed = discord.Embed(title="🛡️ ¡Robo Bloqueado!", color=0x3498DB)
        embed.description = (
            f"**{usuario.mention}** tenía un **Escudo Anti-Robo** activo.\n"
            f"¡Tu intento de robo fue bloqueado y el escudo se consumió!"
        )
        await interaction.response.send_message(embed=embed)
        return

    success = random.random() < 0.40

    if success:
        pct = random.uniform(0.10, 0.40)
        stolen = max(1, int(victim_balance * pct))
        stolen = min(stolen, victim_balance)
        await update_balance(victim_id, -stolen)
        await update_balance(robber_id, stolen)
        await track_mission(robber_id, "rob_success")
        robber_balance = await get_balance(robber_id)
        embed = discord.Embed(title="🦹 ¡Robo Exitoso!", color=0x00FF88)
        embed.description = (
            f"¡Le robaste **{stolen:,}** 🪙 a **{usuario.mention}**!\n\n"
            f"Tu saldo: **{robber_balance:,}** 🪙"
        )
    else:
        fine = max(1, int(victim_balance * 0.10))
        robber_balance = await get_balance(robber_id)
        fine = min(fine, robber_balance)
        await update_balance(robber_id, -fine)
        new_robber_balance = robber_balance - fine
        embed = discord.Embed(title="🚔 ¡Te Atraparon!", color=0xFF4444)
        embed.description = (
            f"Intentaste robar a **{usuario.mention}** pero te atraparon.\n"
            f"Multa: **{fine:,}** 🪙\n\n"
            f"Tu saldo: **{new_robber_balance:,}** 🪙"
        )

    await interaction.response.send_message(embed=embed)


@tree.command(name="addmoney", description="[ADMIN] Añade monedas a un usuario")
@app_commands.describe(usuario="Usuario objetivo", cantidad="Cantidad a añadir")
@app_commands.default_permissions(administrator=True)
async def addmoney(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    if cantidad <= 0:
        await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
        return
    target_id = str(usuario.id)
    await get_or_create_user(target_id, usuario.name)
    await update_balance(target_id, cantidad)
    new_balance = await get_balance(target_id)
    embed = discord.Embed(title="✅ Dinero Añadido", color=0x00FF88)
    embed.description = f"Se añadieron **{cantidad:,}** 🪙 a {usuario.mention}.\nNuevo saldo: **{new_balance:,}** 🪙"
    await interaction.response.send_message(embed=embed)


@tree.command(name="removemoney", description="[ADMIN] Quita monedas a un usuario")
@app_commands.describe(usuario="Usuario objetivo", cantidad="Cantidad a quitar")
@app_commands.default_permissions(administrator=True)
async def removemoney(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    if cantidad <= 0:
        await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
        return
    target_id = str(usuario.id)
    await get_or_create_user(target_id, usuario.name)
    current = await get_balance(target_id)
    deduct = min(cantidad, current)
    await update_balance(target_id, -deduct)
    new_balance = await get_balance(target_id)
    embed = discord.Embed(title="✅ Dinero Eliminado", color=0xFFAA00)
    embed.description = f"Se quitaron **{deduct:,}** 🪙 a {usuario.mention}.\nNuevo saldo: **{new_balance:,}** 🪙"
    await interaction.response.send_message(embed=embed)


@tree.command(name="shop", description="Muestra los objetos disponibles en la tienda")
async def shop(interaction: discord.Interaction):
    embed = discord.Embed(title="🏪 Tienda del Casino", color=0x9B59B6)
    embed.description = "Usa `/buy <id_item>` para comprar. Los roles se usan con `/collect`.\n"

    categorias = {
        "proteccion": "🛡️ Protección",
        "rol": "👑 Roles con /collect",
        "decorativo": "🎭 Decorativos",
    }

    for cat_key, cat_name in categorias.items():
        items_in_cat = [(k, v) for k, v in SHOP_ITEMS.items() if v["category"] == cat_key]
        if not items_in_cat:
            continue
        lines = []
        for item_id, item in items_in_cat:
            lines.append(f"**{item['name']}** — {item['price']:,} 🪙\n{item['description']}\n`ID: {item_id}`")
        embed.add_field(name=cat_name, value="\n\n".join(lines), inline=False)

    await interaction.response.send_message(embed=embed)


@tree.command(name="buy", description="Compra un objeto de la tienda")
@app_commands.describe(item="ID del objeto a comprar")
async def buy(interaction: discord.Interaction, item: str):
    item = item.lower().strip()
    if item not in SHOP_ITEMS:
        ids = ", ".join(f"`{k}`" for k in SHOP_ITEMS.keys())
        await interaction.response.send_message(f"❌ Objeto no encontrado. IDs válidos: {ids}", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)

    item_data = SHOP_ITEMS[item]
    bal = await get_balance(user_id)

    if bal < item_data["price"]:
        embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
        embed.description = f"Necesitas **{item_data['price']:,}** 🪙 y tienes **{bal:,}** 🪙."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await update_balance(user_id, -item_data["price"])
    await add_to_inventory(user_id, item)
    new_balance = await get_balance(user_id)

    embed = discord.Embed(title="🛍️ ¡Compra Exitosa!", color=0x00FF88)
    desc = (
        f"Compraste **{item_data['name']}**.\n"
        f"{item_data['description']}\n\n"
        f"Gastaste: **{item_data['price']:,}** 🪙\n"
        f"Saldo restante: **{new_balance:,}** 🪙"
    )
    if item_data["category"] == "rol":
        desc += "\n\n💡 Usa `/collect` para reclamar tus ganancias de rol."
    if item_data["category"] == "proteccion":
        desc += "\n\n💡 Se activa automáticamente si alguien intenta robarte."
    embed.description = desc
    await interaction.response.send_message(embed=embed)


@tree.command(name="inventory", description="Muestra tu inventario")
async def inventory(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)
    items = await get_inventory(user_id)

    embed = discord.Embed(title=f"🎒 Inventario de {interaction.user.name}", color=0x3498DB)
    if not items:
        embed.description = "Tu inventario está vacío.\nUsa `/shop` para ver los objetos disponibles."
    else:
        for item_id, qty in items:
            item_data = SHOP_ITEMS.get(item_id, {"name": item_id, "description": "Objeto desconocido"})
            embed.add_field(
                name=f"{item_data['name']} x{qty}",
                value=item_data["description"],
                inline=False
            )
    await interaction.response.send_message(embed=embed)


@tree.command(name="leaderboard", description="Muestra el ranking de los usuarios más ricos")
async def leaderboard(interaction: discord.Interaction):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10"
        ) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await interaction.response.send_message("❌ No hay usuarios registrados aún.", ephemeral=True)
        return

    medals = ["🥇", "🥈", "🥉"]
    embed = discord.Embed(title="🏆 Ranking del Casino", color=0xFFD700)
    description = ""
    for i, (username, bal) in enumerate(rows):
        prefix = medals[i] if i < 3 else f"**#{i+1}**"
        description += f"{prefix} **{username}** — {bal:,} 🪙\n"
    embed.description = description
    embed.set_footer(text="Top 10 jugadores más ricos")
    await interaction.response.send_message(embed=embed)


SUITS = ["♠️", "♥️", "♦️", "♣️"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

def new_deck():
    deck = [(r, s) for s in SUITS for r in RANKS]
    random.shuffle(deck)
    return deck

def card_value(rank):
    if rank in ("J", "Q", "K"):
        return 10
    if rank == "A":
        return 11
    return int(rank)

def hand_total(hand):
    total = sum(card_value(r) for r, _ in hand)
    aces = sum(1 for r, _ in hand if r == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def fmt_hand(hand):
    return " ".join(f"`{r}{s}`" for r, s in hand)

def bj_embed(player_hand, dealer_hand, bet, reveal_dealer=False, result_msg=None):
    color = 0xFFD700
    if result_msg:
        if "¡GANASTE" in result_msg or "BLACKJACK" in result_msg:
            color = 0x00FF88
        elif "Perdiste" in result_msg or "pasaste" in result_msg:
            color = 0xFF4444
        else:
            color = 0xFFAA00

    embed = discord.Embed(title="🃏 Blackjack", color=color)

    if reveal_dealer:
        dealer_total = hand_total(dealer_hand)
        embed.add_field(name=f"Dealer — {dealer_total}", value=fmt_hand(dealer_hand), inline=False)
    else:
        hidden = f"`{dealer_hand[0][0]}{dealer_hand[0][1]}` `🂠`"
        embed.add_field(name="Dealer", value=hidden, inline=False)

    player_total = hand_total(player_hand)
    embed.add_field(name=f"Tu mano — {player_total}", value=fmt_hand(player_hand), inline=False)
    embed.add_field(name="Apuesta", value=f"**{bet:,}** 🪙", inline=True)

    if result_msg:
        embed.add_field(name="Resultado", value=result_msg, inline=False)

    return embed


class BlackjackView(discord.ui.View):
    def __init__(self, user_id, bet, player_hand, dealer_hand, deck, balance):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.bet = bet
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.deck = deck
        self.balance = balance

    async def end_game(self, interaction, result_msg, payout):
        await update_balance(self.user_id, payout)
        new_balance = await get_balance(self.user_id)
        embed = bj_embed(self.player_hand, self.dealer_hand, self.bet, reveal_dealer=True,
                         result_msg=f"{result_msg}\nSaldo: **{new_balance:,}** 🪙")
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="🃏 Pedir (Hit)", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("Este no es tu juego.", ephemeral=True)
            return
        self.player_hand.append(self.deck.pop())
        total = hand_total(self.player_hand)
        if total > 21:
            await self.end_game(interaction, f"💥 ¡Te pasaste con {total}! Perdiste **{self.bet:,}** 🪙.", 0)
        elif total == 21:
            await self.stand_logic(interaction)
        else:
            embed = bj_embed(self.player_hand, self.dealer_hand, self.bet)
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="✋ Plantarse (Stand)", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("Este no es tu juego.", ephemeral=True)
            return
        await self.stand_logic(interaction)

    async def stand_logic(self, interaction):
        while hand_total(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())

        player_total = hand_total(self.player_hand)
        dealer_total = hand_total(self.dealer_hand)

        if dealer_total > 21:
            await track_mission(self.user_id, "blackjack_won")
            await self.end_game(interaction, f"🎉 ¡El dealer se pasó ({dealer_total})! ¡GANASTE **{self.bet:,}** 🪙!", self.bet)
        elif player_total > dealer_total:
            await track_mission(self.user_id, "blackjack_won")
            await self.end_game(interaction, f"🎉 ¡GANASTE! {player_total} vs {dealer_total}. +**{self.bet:,}** 🪙", self.bet)
        elif player_total < dealer_total:
            await self.end_game(interaction, f"😔 Perdiste. {player_total} vs {dealer_total}. -**{self.bet:,}** 🪙", 0)
        else:
            await update_balance(self.user_id, self.bet)
            new_balance = await get_balance(self.user_id)
            embed = bj_embed(self.player_hand, self.dealer_hand, self.bet, reveal_dealer=True,
                             result_msg=f"🤝 ¡Empate! Se devuelve tu apuesta.\nSaldo: **{new_balance:,}** 🪙")
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


@tree.command(name="blackjack", description="Juega al blackjack contra el dealer")
@app_commands.describe(cantidad="Cantidad a apostar")
async def blackjack(interaction: discord.Interaction, cantidad: int):
    if cantidad <= 0:
        await interaction.response.send_message("❌ La apuesta debe ser mayor a 0.", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)
    bal = await get_balance(user_id)

    if bal < cantidad:
        embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
        embed.description = f"Tienes **{bal:,}** 🪙 y quieres apostar **{cantidad:,}** 🪙."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await update_balance(user_id, -cantidad)

    deck = new_deck()
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    player_total = hand_total(player_hand)

    if player_total == 21:
        payout = int(cantidad * 1.5)
        await update_balance(user_id, cantidad + payout)
        await track_mission(user_id, "blackjack_won")
        new_balance = await get_balance(user_id)
        embed = bj_embed(player_hand, dealer_hand, cantidad, reveal_dealer=True,
                         result_msg=f"🃏 ¡BLACKJACK! Ganas **{payout:,}** 🪙 extra!\nSaldo: **{new_balance:,}** 🪙")
        await interaction.response.send_message(embed=embed)
        return

    view = BlackjackView(user_id, cantidad, player_hand, dealer_hand, deck, bal)
    embed = bj_embed(player_hand, dealer_hand, cantidad)
    await interaction.response.send_message(embed=embed, view=view)


class CoinflipChallengeView(discord.ui.View):
    def __init__(self, challenger_id: str, challenger_name: str, challenged: discord.Member, bet: int):
        super().__init__(timeout=60)
        self.challenger_id = challenger_id
        self.challenger_name = challenger_name
        self.challenged = challenged
        self.bet = bet
        self.resolved = False

    @discord.ui.button(label="✅ Aceptar", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.challenged.id:
            await interaction.response.send_message("Este reto no es para ti.", ephemeral=True)
            return
        if self.resolved:
            return
        self.resolved = True

        challenged_id = str(self.challenged.id)
        challenged_balance = await get_balance(challenged_id)
        if challenged_balance < self.bet:
            for item in self.children:
                item.disabled = True
            embed = discord.Embed(title="❌ Sin Fondos", color=0xFF4444)
            embed.description = f"{self.challenged.mention} no tiene suficientes monedas para aceptar el reto."
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
            return

        await update_balance(self.challenger_id, -self.bet)
        await update_balance(challenged_id, -self.bet)

        flip = random.choice(["cara", "cruz"])
        winner_side = random.choice(["cara", "cruz"])
        challenger_pick = "cara"
        challenged_pick = "cruz"

        if winner_side == challenger_pick:
            winner_id = self.challenger_id
            winner_name = self.challenger_name
            loser_mention = self.challenged.mention
        else:
            winner_id = challenged_id
            winner_name = self.challenged.name
            loser_mention = f"<@{self.challenger_id}>"

        total_prize = self.bet * 2
        await update_balance(winner_id, total_prize)
        winner_balance = await get_balance(winner_id)

        flip_emoji = "🪙" if flip == "cara" else "🌑"
        embed = discord.Embed(title="🪙 ¡Resultado del Cara o Cruz!", color=0xFFD700)
        embed.description = (
            f"La moneda cayó en **{flip_emoji} {flip.upper()}**\n\n"
            f"🎩 {self.challenger_name} apostó por **{challenger_pick}**\n"
            f"🎮 {self.challenged.name} apostó por **{challenged_pick}**\n\n"
            f"🏆 **¡{winner_name} gana {total_prize:,} 🪙!**\n"
            f"😔 {loser_mention} pierde **{self.bet:,}** 🪙\n\n"
            f"Saldo del ganador: **{winner_balance:,}** 🪙"
        )
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="❌ Rechazar", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.challenged.id:
            await interaction.response.send_message("Este reto no es para ti.", ephemeral=True)
            return
        if self.resolved:
            return
        self.resolved = True
        for item in self.children:
            item.disabled = True
        embed = discord.Embed(title="🚫 Reto Rechazado", color=0xFF4444)
        embed.description = f"**{self.challenged.name}** rechazó el reto de cara o cruz."
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def on_timeout(self):
        self.resolved = True
        for item in self.children:
            item.disabled = True


@tree.command(name="coinflip", description="Reta a otro usuario a cara o cruz por monedas")
@app_commands.describe(usuario="El usuario al que quieres retar", cantidad="Cantidad a apostar")
async def coinflip(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    if cantidad <= 0:
        await interaction.response.send_message("❌ La apuesta debe ser mayor a 0.", ephemeral=True)
        return
    if usuario.id == interaction.user.id:
        await interaction.response.send_message("❌ No puedes retarte a ti mismo.", ephemeral=True)
        return
    if usuario.bot:
        await interaction.response.send_message("❌ No puedes retar a un bot.", ephemeral=True)
        return

    challenger_id = str(interaction.user.id)
    await get_or_create_user(challenger_id, interaction.user.name)
    await get_or_create_user(str(usuario.id), usuario.name)

    challenger_balance = await get_balance(challenger_id)
    if challenger_balance < cantidad:
        embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
        embed.description = f"Necesitas **{cantidad:,}** 🪙 y tienes **{challenger_balance:,}** 🪙."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(title="🪙 ¡Reto de Cara o Cruz!", color=0x9B59B6)
    embed.description = (
        f"**{interaction.user.mention}** reta a **{usuario.mention}**\n\n"
        f"💰 Apuesta: **{cantidad:,}** 🪙 cada uno\n"
        f"🏆 Premio total: **{cantidad*2:,}** 🪙\n\n"
        f"🎩 {interaction.user.name} → **CARA**\n"
        f"🎮 {usuario.name} → **CRUZ**\n\n"
        f"{usuario.mention}, tienes **60 segundos** para aceptar o rechazar."
    )

    view = CoinflipChallengeView(
        challenger_id=challenger_id,
        challenger_name=interaction.user.name,
        challenged=usuario,
        bet=cantidad,
    )
    await interaction.response.send_message(embed=embed, view=view)


class DuelChallengeView(discord.ui.View):
    def __init__(self, challenger_id: str, challenger_name: str, challenged: discord.Member, bet: int):
        super().__init__(timeout=60)
        self.challenger_id = challenger_id
        self.challenger_name = challenger_name
        self.challenged = challenged
        self.bet = bet
        self.resolved = False

    @discord.ui.button(label="⚔️ Aceptar Duelo", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.challenged.id:
            await interaction.response.send_message("Este duelo no es para ti.", ephemeral=True)
            return
        if self.resolved:
            return
        self.resolved = True

        challenged_id = str(self.challenged.id)
        challenged_balance = await get_balance(challenged_id)
        if challenged_balance < self.bet:
            for item in self.children:
                item.disabled = True
            embed = discord.Embed(title="❌ Sin Fondos", color=0xFF4444)
            embed.description = f"{self.challenged.mention} no tiene suficientes monedas para aceptar el duelo."
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
            return

        await update_balance(self.challenger_id, -self.bet)
        await update_balance(challenged_id, -self.bet)

        dice_challenger = random.randint(1, 6)
        dice_challenged = random.randint(1, 6)

        def dice_emoji(n):
            return ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣"][n - 1]

        total_prize = self.bet * 2

        if dice_challenger > dice_challenged:
            winner_id = self.challenger_id
            winner_name = self.challenger_name
            loser_name = self.challenged.name
            result_line = f"🏆 **¡{self.challenger_name} gana el duelo!**"
        elif dice_challenged > dice_challenger:
            winner_id = challenged_id
            winner_name = self.challenged.name
            loser_name = self.challenger_name
            result_line = f"🏆 **¡{self.challenged.name} gana el duelo!**"
        else:
            await update_balance(self.challenger_id, self.bet)
            await update_balance(challenged_id, self.bet)
            embed = discord.Embed(title="⚔️ ¡Duelo de Dados!", color=0xFFAA00)
            embed.description = (
                f"{dice_emoji(dice_challenger)} **{self.challenger_name}** tiró **{dice_challenger}**\n"
                f"{dice_emoji(dice_challenged)} **{self.challenged.name}** tiró **{dice_challenged}**\n\n"
                f"🤝 **¡Empate!** Se devuelve la apuesta a ambos."
            )
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
            return

        await update_balance(winner_id, total_prize)
        winner_balance = await get_balance(winner_id)

        embed = discord.Embed(title="⚔️ ¡Duelo de Dados — Resultado!", color=0x00FF88)
        embed.description = (
            f"{dice_emoji(dice_challenger)} **{self.challenger_name}** tiró **{dice_challenger}**\n"
            f"{dice_emoji(dice_challenged)} **{self.challenged.name}** tiró **{dice_challenged}**\n\n"
            f"{result_line}\n"
            f"💰 Gana **{total_prize:,}** 🪙\n"
            f"😔 **{loser_name}** pierde **{self.bet:,}** 🪙\n\n"
            f"Saldo del ganador: **{winner_balance:,}** 🪙"
        )
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="🏳️ Rechazar", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.challenged.id:
            await interaction.response.send_message("Este duelo no es para ti.", ephemeral=True)
            return
        if self.resolved:
            return
        self.resolved = True
        for item in self.children:
            item.disabled = True
        embed = discord.Embed(title="🏳️ Duelo Rechazado", color=0xFF4444)
        embed.description = f"**{self.challenged.name}** rehusó el duelo. ¡Cobarde!"
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def on_timeout(self):
        self.resolved = True
        for item in self.children:
            item.disabled = True


@tree.command(name="duel", description="Reta a otro usuario a un duelo de dados")
@app_commands.describe(usuario="El usuario al que quieres retar", cantidad="Cantidad a apostar")
async def duel(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    if cantidad <= 0:
        await interaction.response.send_message("❌ La apuesta debe ser mayor a 0.", ephemeral=True)
        return
    if usuario.id == interaction.user.id:
        await interaction.response.send_message("❌ No puedes retarte a ti mismo.", ephemeral=True)
        return
    if usuario.bot:
        await interaction.response.send_message("❌ No puedes retar a un bot.", ephemeral=True)
        return

    challenger_id = str(interaction.user.id)
    await get_or_create_user(challenger_id, interaction.user.name)
    await get_or_create_user(str(usuario.id), usuario.name)

    challenger_balance = await get_balance(challenger_id)
    if challenger_balance < cantidad:
        embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
        embed.description = f"Necesitas **{cantidad:,}** 🪙 y tienes **{challenger_balance:,}** 🪙."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(title="⚔️ ¡Duelo de Dados!", color=0xE74C3C)
    embed.description = (
        f"**{interaction.user.mention}** reta a **{usuario.mention}** a un duelo de dados.\n\n"
        f"🎲 Cada jugador lanzará un dado del 1 al 6\n"
        f"🏆 El mayor número gana todo\n"
        f"🤝 Si empatan, se devuelve la apuesta\n\n"
        f"💰 Apuesta: **{cantidad:,}** 🪙 cada uno\n"
        f"🏆 Premio total: **{cantidad*2:,}** 🪙\n\n"
        f"{usuario.mention}, tienes **60 segundos** para aceptar o rechazar."
    )

    view = DuelChallengeView(
        challenger_id=challenger_id,
        challenger_name=interaction.user.name,
        challenged=usuario,
        bet=cantidad,
    )
    await interaction.response.send_message(embed=embed, view=view)


def generate_crash_point() -> float:
    r = random.random()
    if r < 0.30:
        return round(random.uniform(1.0, 1.5), 2)
    elif r < 0.55:
        return round(random.uniform(1.5, 2.5), 2)
    elif r < 0.75:
        return round(random.uniform(2.5, 5.0), 2)
    elif r < 0.88:
        return round(random.uniform(5.0, 10.0), 2)
    elif r < 0.95:
        return round(random.uniform(10.0, 20.0), 2)
    else:
        return round(random.uniform(20.0, 50.0), 2)


class CrashView(discord.ui.View):
    def __init__(self, user_id: str, bet: int, crash_point: float):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.bet = bet
        self.crash_point = crash_point
        self.current_mult = 1.0
        self.cashed_out = False
        self.finished = False
        self.message: discord.Message | None = None

    def make_embed(self, crashed=False, cashed_out=False) -> discord.Embed:
        mult_str = f"{self.current_mult:.2f}x"
        if cashed_out:
            winnings = int(self.bet * self.current_mult)
            embed = discord.Embed(title="💸 ¡Cash Out Exitoso!", color=0x00FF88)
            embed.description = (
                f"Te retiraste en **{mult_str}** 🚀\n\n"
                f"💰 Ganaste **{winnings:,}** 🪙"
            )
        elif crashed:
            embed = discord.Embed(title="💥 ¡CRASH!", color=0xFF4444)
            embed.description = (
                f"El juego crasheó en **{mult_str}** 💀\n\n"
                f"😔 Perdiste **{self.bet:,}** 🪙"
            )
        else:
            winnings = int(self.bet * self.current_mult)
            embed = discord.Embed(title="📈 Crash — ¡Retírate antes del crash!", color=0x9B59B6)
            embed.description = (
                f"Multiplicador: **{mult_str}** 🚀\n"
                f"Apuesta: **{self.bet:,}** 🪙\n\n"
                f"Si te retiras ahora: **{winnings:,}** 🪙"
            )
        return embed

    async def run(self):
        await asyncio.sleep(2.0)
        step = 0.1
        while not self.cashed_out and not self.finished:
            self.current_mult = round(self.current_mult + step, 2)
            if self.current_mult > 5.0:
                step = 0.3
            elif self.current_mult > 2.0:
                step = 0.2

            if self.current_mult >= self.crash_point:
                self.finished = True
                for item in self.children:
                    item.disabled = True
                if self.message:
                    try:
                        await self.message.edit(embed=self.make_embed(crashed=True), view=self)
                    except Exception:
                        pass
                self.stop()
                return

            if self.message:
                try:
                    await self.message.edit(embed=self.make_embed(), view=self)
                except Exception:
                    pass
            await asyncio.sleep(1.5)

    @discord.ui.button(label="💸 Cash Out", style=discord.ButtonStyle.success)
    async def cashout(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("Este no es tu juego.", ephemeral=True)
            return
        if self.finished or self.cashed_out:
            await interaction.response.send_message("El juego ya terminó.", ephemeral=True)
            return

        self.cashed_out = True
        self.finished = True
        winnings = int(self.bet * self.current_mult)
        await update_balance(self.user_id, winnings)
        new_balance = await get_balance(self.user_id)

        for item in self.children:
            item.disabled = True

        embed = self.make_embed(cashed_out=True)
        embed.add_field(name="Saldo actual", value=f"**{new_balance:,}** 🪙", inline=False)
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


@tree.command(name="crash", description="Apuesta y retírate antes de que crashee el multiplicador")
@app_commands.describe(cantidad="Cantidad a apostar")
async def crash(interaction: discord.Interaction, cantidad: int):
    if cantidad <= 0:
        await interaction.response.send_message("❌ La apuesta debe ser mayor a 0.", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)
    bal = await get_balance(user_id)

    if bal < cantidad:
        embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
        embed.description = f"Tienes **{bal:,}** 🪙 y quieres apostar **{cantidad:,}** 🪙."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await update_balance(user_id, -cantidad)
    crash_point = generate_crash_point()

    view = CrashView(user_id=user_id, bet=cantidad, crash_point=crash_point)
    embed = view.make_embed()
    await interaction.response.send_message(embed=embed, view=view)
    view.message = await interaction.original_response()
    await track_mission(user_id, "crash_played")
    asyncio.create_task(view.run())


@tree.command(name="store", description="Muestra la tienda del casino (alias de /shop)")
async def store(interaction: discord.Interaction):
    embed = discord.Embed(title="🏪 Tienda del Casino", color=0x9B59B6)
    embed.description = "Usa `/buy <id_item>` para comprar. Los roles se usan con `/collect`.\n"

    categorias = {
        "proteccion": "🛡️ Protección",
        "rol": "👑 Roles con /collect",
        "decorativo": "🎭 Decorativos",
    }

    for cat_key, cat_name in categorias.items():
        items_in_cat = [(k, v) for k, v in SHOP_ITEMS.items() if v["category"] == cat_key]
        if not items_in_cat:
            continue
        lines = []
        for item_id, item in items_in_cat:
            lines.append(f"**{item['name']}** — {item['price']:,} 🪙\n{item['description']}\n`ID: {item_id}`")
        embed.add_field(name=cat_name, value="\n\n".join(lines), inline=False)

    await interaction.response.send_message(embed=embed)


@tree.command(name="iteminfo", description="Muestra los detalles completos de un objeto de la tienda")
@app_commands.describe(item="ID del objeto a consultar")
async def iteminfo(interaction: discord.Interaction, item: str):
    item = item.lower().strip()
    if item not in SHOP_ITEMS:
        ids = ", ".join(f"`{k}`" for k in SHOP_ITEMS.keys())
        await interaction.response.send_message(
            f"❌ Objeto no encontrado. IDs válidos:\n{ids}", ephemeral=True
        )
        return

    data = SHOP_ITEMS[item]
    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)
    qty = await get_item_quantity(user_id, item)

    cat_labels = {
        "proteccion": "🛡️ Protección",
        "rol": "👑 Rol con /collect",
        "decorativo": "🎭 Decorativo",
    }

    color_map = {"proteccion": 0x3498DB, "rol": 0xFFD700, "decorativo": 0x9B59B6}
    embed = discord.Embed(
        title=data["name"],
        color=color_map.get(data["category"], 0xFFFFFF)
    )
    embed.add_field(name="Descripción", value=data["description"], inline=False)
    embed.add_field(name="Precio", value=f"**{data['price']:,}** 🪙", inline=True)
    embed.add_field(name="Categoría", value=cat_labels.get(data["category"], data["category"]), inline=True)
    embed.add_field(name="En tu inventario", value=f"**{qty}** unidades", inline=True)

    if data["category"] == "rol":
        embed.add_field(
            name="💰 Bonus de /collect",
            value=f"+**{data['collect_bonus']:,}** 🪙 cada **{data['collect_hours']}h**",
            inline=False
        )
        embed.add_field(
            name="📋 Cómo funciona",
            value=(
                "• Compra el rol con `/buy`\n"
                "• Usa `/collect` para reclamar tus ganancias\n"
                "• Si tienes varios roles, los bonuses se suman\n"
                "• El cooldown es el menor entre tus roles activos"
            ),
            inline=False
        )
    elif data["category"] == "proteccion":
        embed.add_field(
            name="📋 Cómo funciona",
            value=(
                "• Se activa automáticamente cuando alguien intenta robarte\n"
                "• Bloquea el robo por completo\n"
                "• Es consumible: se gasta 1 unidad por cada robo bloqueado\n"
                "• Puedes tener múltiples unidades en inventario"
            ),
            inline=False
        )

    embed.set_footer(text=f"ID del objeto: {item}")
    await interaction.response.send_message(embed=embed)


@tree.command(name="missions", description="Muestra tus misiones diarias y su progreso")
async def missions(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)
    data = await get_missions_data(user_id)

    embed = discord.Embed(title="📋 Misiones Diarias", color=0xE67E22)
    embed.description = "Completa misiones cada día para ganar monedas extra. ¡Se reinician a medianoche!\n"

    total_earned = sum(m["reward"] for m in data if m["completed"])
    total_available = sum(m["reward"] for m in data)

    for m in data:
        bar_filled = int((m["progress"] / m["goal"]) * 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        status = "✅ **COMPLETADA**" if m["completed"] else f"`[{bar}]` {m['progress']}/{m['goal']}"
        embed.add_field(
            name=f"{m['name']} — +{m['reward']:,} 🪙",
            value=f"{m['description']}\n{status}",
            inline=False
        )

    embed.set_footer(text=f"Ganadas hoy: {total_earned:,} / {total_available:,} 🪙")
    await interaction.response.send_message(embed=embed)


@tree.command(name="use", description="Usa un objeto de tu inventario")
@app_commands.describe(item="ID del objeto a usar")
async def use(interaction: discord.Interaction, item: str):
    item = item.lower().strip()
    if item not in SHOP_ITEMS:
        ids = ", ".join(f"`{k}`" for k in SHOP_ITEMS.keys())
        await interaction.response.send_message(
            f"❌ Objeto no encontrado. IDs válidos:\n{ids}", ephemeral=True
        )
        return

    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)
    qty = await get_item_quantity(user_id, item)

    if qty == 0:
        embed = discord.Embed(title="❌ Sin Objeto", color=0xFF4444)
        embed.description = f"No tienes **{SHOP_ITEMS[item]['name']}** en tu inventario.\nCómpralo en `/shop`."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    item_data = SHOP_ITEMS[item]

    if item_data["category"] == "decorativo":
        flavor = USE_FLAVOR.get(item, f"Usas **{item_data['name']}**.")
        embed = discord.Embed(title=f"✨ Usando {item_data['name']}", color=0x9B59B6)
        embed.description = flavor
        embed.set_footer(text=f"Tienes {qty} en tu inventario")
        await interaction.response.send_message(embed=embed)

    elif item == "anti_rob":
        embed = discord.Embed(title="🛡️ Escudo Anti-Robo", color=0x3498DB)
        embed.description = (
            f"Tu escudo está **activo** y listo.\n\n"
            f"🔒 Se activará automáticamente la próxima vez que alguien intente robarte.\n"
            f"💡 Es consumible: se gastará 1 unidad por robo bloqueado.\n\n"
            f"Tienes **{qty}** escudos en tu inventario."
        )
        await interaction.response.send_message(embed=embed)

    elif item_data["category"] == "rol":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT last_collect FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                last_collect = row[0] if row else None

        now = datetime.utcnow()
        cooldown_hours = item_data["collect_hours"]
        if last_collect:
            last_dt = datetime.fromisoformat(last_collect)
            diff = now - last_dt
            if diff < timedelta(hours=cooldown_hours):
                remaining = timedelta(hours=cooldown_hours) - diff
                hrs, rem = divmod(int(remaining.total_seconds()), 3600)
                mins = rem // 60
                next_collect = f"en **{hrs}h {mins}m**"
            else:
                next_collect = "**¡Ahora mismo!** Usa `/collect`"
        else:
            next_collect = "**¡Ahora mismo!** Usa `/collect`"

        embed = discord.Embed(title=f"👑 {item_data['name']}", color=0xFFD700)
        embed.description = (
            f"**Estado:** Activo ✅\n"
            f"**Bonus de /collect:** +**{item_data['collect_bonus']:,}** 🪙 cada **{cooldown_hours}h**\n"
            f"**Próximo collect:** {next_collect}\n\n"
            f"Tienes **{qty}** unidades en inventario.\n"
            f"💡 Usa `/collect` para reclamar tus ganancias."
        )
        await interaction.response.send_message(embed=embed)


@tree.command(name="gift", description="Regala un objeto de tu inventario a otro usuario")
@app_commands.describe(usuario="El usuario que recibirá el regalo", item="ID del objeto a regalar")
async def gift(interaction: discord.Interaction, usuario: discord.Member, item: str):
    item = item.lower().strip()
    if item not in SHOP_ITEMS:
        ids = ", ".join(f"`{k}`" for k in SHOP_ITEMS.keys())
        await interaction.response.send_message(f"❌ Objeto no encontrado. IDs válidos:\n{ids}", ephemeral=True)
        return
    if usuario.id == interaction.user.id:
        await interaction.response.send_message("❌ No puedes regalarte objetos a ti mismo.", ephemeral=True)
        return
    if usuario.bot:
        await interaction.response.send_message("❌ No puedes regalarle a un bot.", ephemeral=True)
        return

    sender_id = str(interaction.user.id)
    receiver_id = str(usuario.id)
    await get_or_create_user(sender_id, interaction.user.name)
    await get_or_create_user(receiver_id, usuario.name)

    qty = await get_item_quantity(sender_id, item)
    if qty == 0:
        embed = discord.Embed(title="❌ Sin Objeto", color=0xFF4444)
        embed.description = f"No tienes **{SHOP_ITEMS[item]['name']}** en tu inventario."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await remove_from_inventory(sender_id, item)
    await add_to_inventory(receiver_id, item)

    item_data = SHOP_ITEMS[item]
    embed = discord.Embed(title="🎁 ¡Regalo Enviado!", color=0x00FF88)
    embed.description = (
        f"**{interaction.user.mention}** le regaló **{item_data['name']}** a **{usuario.mention}**.\n\n"
        f"{item_data['description']}\n\n"
        f"Te quedan **{qty - 1}** unidades en inventario."
    )
    await interaction.response.send_message(embed=embed)


@tree.command(name="sell", description="Vende un objeto de tu inventario por el 50% de su valor")
@app_commands.describe(item="ID del objeto a vender")
async def sell(interaction: discord.Interaction, item: str):
    item = item.lower().strip()
    if item not in SHOP_ITEMS:
        ids = ", ".join(f"`{k}`" for k in SHOP_ITEMS.keys())
        await interaction.response.send_message(f"❌ Objeto no encontrado. IDs válidos:\n{ids}", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)

    qty = await get_item_quantity(user_id, item)
    if qty == 0:
        embed = discord.Embed(title="❌ Sin Objeto", color=0xFF4444)
        embed.description = f"No tienes **{SHOP_ITEMS[item]['name']}** en tu inventario."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    item_data = SHOP_ITEMS[item]
    sell_price = item_data["price"] // 2

    await remove_from_inventory(user_id, item)
    await update_balance(user_id, sell_price)
    new_balance = await get_balance(user_id)

    embed = discord.Embed(title="💰 Objeto Vendido", color=0xFFD700)
    embed.description = (
        f"Vendiste **{item_data['name']}** por **{sell_price:,}** 🪙 (50% del precio original).\n\n"
        f"Saldo actual: **{new_balance:,}** 🪙\n"
        f"Te quedan **{qty - 1}** unidades en inventario."
    )
    await interaction.response.send_message(embed=embed)


if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: Falta la variable de entorno DISCORD_TOKEN")
        exit(1)
    client.run(TOKEN)
