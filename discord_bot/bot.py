import discord
from discord import app_commands
import aiosqlite
import random
import os
from datetime import datetime, timedelta

TOKEN = os.environ.get("DISCORD_TOKEN")
DB_PATH = "discord_bot/casino.db"

SHOP_ITEMS = {
    "vip_card": {"name": "Tarjeta VIP", "price": 2000, "description": "Acceso VIP al casino. ¡Lujo puro!"},
    "lucky_charm": {"name": "Amuleto de la Suerte", "price": 1000, "description": "+10% de suerte (decorativo)"},
    "golden_chip": {"name": "Ficha Dorada", "price": 5000, "description": "La ficha más exclusiva del casino"},
    "cocktail": {"name": "Cóctel de Casino", "price": 300, "description": "Una bebida elegante para el jugador"},
    "sunglasses": {"name": "Gafas de Poker", "price": 750, "description": "Para que nadie lea tu cara"},
}

RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK_NUMBERS = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}

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
                last_daily TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                item_id TEXT,
                quantity INTEGER DEFAULT 1,
                UNIQUE(user_id, item_id)
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


async def set_balance(user_id: str, new_balance: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        await db.commit()


async def get_inventory(user_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT item_id, quantity FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchall()


async def add_to_inventory(user_id: str, item_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO inventory (user_id, item_id, quantity) VALUES (?, ?, 1) ON CONFLICT(user_id, item_id) DO UPDATE SET quantity = quantity + 1",
            (user_id, item_id)
        )
        await db.commit()


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
        await db.execute("UPDATE users SET balance = balance + 500, last_daily = ? WHERE user_id = ?", (now.isoformat(), user_id))
        await db.commit()

    balance = await get_balance(user_id)
    embed = discord.Embed(title="🎁 ¡Recompensa Diaria!", color=0x00FF88)
    embed.description = f"¡Recibiste **500** 🪙!\nSaldo actual: **{balance:,}** 🪙"
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
        embed.description = f"No tienes suficiente dinero.\nTienes **{sender_balance:,}** 🪙 y quieres enviar **{cantidad:,}** 🪙."
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
    balance = await get_balance(user_id)

    if balance < cantidad:
        embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
        embed.description = f"No tienes suficiente dinero.\nTienes **{balance:,}** 🪙 y quieres apostar **{cantidad:,}** 🪙."
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
        new_balance = balance + cantidad
        embed = discord.Embed(title="🎰 ¡GANASTE!", color=0x00FF88)
        embed.description = (
            f"La ruleta cayó en **{emoji} {numero} ({resultado_color})**\n"
            f"Apostaste: **{color}** ✅\n\n"
            f"💰 Ganaste **{cantidad:,}** 🪙\n"
            f"Saldo actual: **{new_balance:,}** 🪙"
        )
    else:
        await update_balance(user_id, -cantidad)
        new_balance = balance - cantidad
        embed = discord.Embed(title="🎰 Perdiste...", color=0xFF4444)
        embed.description = (
            f"La ruleta cayó en **{emoji} {numero} ({resultado_color})**\n"
            f"Apostaste: **{color}** ❌\n\n"
            f"💸 Perdiste **{cantidad:,}** 🪙\n"
            f"Saldo actual: **{new_balance:,}** 🪙"
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
    embed.description = "Usa `/buy <id_item>` para comprar un objeto.\n\n"
    for item_id, item in SHOP_ITEMS.items():
        embed.add_field(
            name=f"{item['name']} — {item['price']:,} 🪙",
            value=f"{item['description']}\n`ID: {item_id}`",
            inline=False
        )
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
    balance = await get_balance(user_id)

    if balance < item_data["price"]:
        embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
        embed.description = f"No tienes suficiente dinero.\nNecesitas **{item_data['price']:,}** 🪙 y tienes **{balance:,}** 🪙."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await update_balance(user_id, -item_data["price"])
    await add_to_inventory(user_id, item)
    new_balance = await get_balance(user_id)

    embed = discord.Embed(title="🛍️ ¡Compra Exitosa!", color=0x00FF88)
    embed.description = (
        f"Compraste **{item_data['name']}**.\n"
        f"{item_data['description']}\n\n"
        f"Gastaste: **{item_data['price']:,}** 🪙\n"
        f"Saldo restante: **{new_balance:,}** 🪙"
    )
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


if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: Falta la variable de entorno DISCORD_TOKEN")
        exit(1)
    client.run(TOKEN)
