import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import aiohttp
import asyncio
import random
import os
from datetime import datetime, timedelta

TOKEN = os.environ.get("NEKO_TOKEN", "")
DB_PATH = "neko_bot/neko.db"

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

SOCIAL_GIFS = {
    "hug":  ["https://media.tenor.com/jEMBIFdSQUgAAAAC/anime-hug.gif",
              "https://media.tenor.com/yI9fB97XWPEAAAAC/hug-anime.gif",
              "https://media.tenor.com/X1eLwnxrGhUAAAAC/anime-hug.gif"],
    "pat":  ["https://media.tenor.com/qFHWjJCFI0EAAAAC/pat-anime.gif",
              "https://media.tenor.com/6TtXZLuHSbkAAAAd/head-pat-anime.gif",
              "https://media.tenor.com/IWq4ywcbWq8AAAAC/pat-head-pat.gif"],
    "kiss": ["https://media.tenor.com/8S9BXQZUAKUAAAAC/anime-kiss.gif",
              "https://media.tenor.com/gXKWbWIBrT8AAAAC/kiss-anime.gif",
              "https://media.tenor.com/GqhKFtBcftMAAAAd/kiss-anime-couple.gif"],
    "slap": ["https://media.tenor.com/WbDSVLRVMkUAAAAC/anime-slap.gif",
              "https://media.tenor.com/bRCptwHijwcAAAAC/slap-anime.gif",
              "https://media.tenor.com/tMhWwBOtR1QAAAAC/slap-anime.gif"],
    "cuddle": ["https://media.tenor.com/x1BV_0NM_oEAAAAC/anime-cuddle.gif",
                "https://media.tenor.com/g8nIsHf4SVUAAAAC/cuddle-couple.gif"],
    "poke":  ["https://media.tenor.com/y-Fzm5o6rGIAAAAC/poke-anime.gif",
               "https://media.tenor.com/kxq1b-MNMV0AAAAC/poke-anime.gif"],
    "bite":  ["https://media.tenor.com/y9r4dBNPFiAAAAAC/anime-bite.gif",
               "https://media.tenor.com/WY5hj-IrdsMAAAAC/anime-bite-neck.gif"],
    "wave":  ["https://media.tenor.com/hiFhcPpLmsgAAAAC/wave-anime.gif",
               "https://media.tenor.com/lDnGhsMlEoQAAAAC/anime-wave.gif"],
}

EIGHTBALL_RESPONSES = [
    ("🟢 Sí, definitivamente.", True),
    ("🟢 Las señales apuntan a sí.", True),
    ("🟢 Con toda certeza.", True),
    ("🟢 Puedes contar con ello.", True),
    ("🟡 Pregunta de nuevo más tarde.", False),
    ("🟡 No puedo predecirlo ahora.", False),
    ("🟡 Concéntrate y vuelve a preguntar.", False),
    ("🔴 No cuentes con ello.", False),
    ("🔴 Mi respuesta es no.", False),
    ("🔴 Las perspectivas no son buenas.", False),
    ("🔴 Muy dudoso.", False),
]

TRIVIA_QUESTIONS = [
    {"q": "¿Cuántos lados tiene un hexágono?", "a": "6", "opts": ["4", "5", "6", "8"]},
    {"q": "¿Cuál es el animal más rápido del mundo?", "a": "Guepardo", "opts": ["León", "Guepardo", "Águila", "Delfín"]},
    {"q": "¿En qué año llegó el hombre a la Luna?", "a": "1969", "opts": ["1965", "1969", "1972", "1981"]},
    {"q": "¿Cuál es el océano más grande del mundo?", "a": "Pacífico", "opts": ["Atlántico", "Índico", "Pacífico", "Ártico"]},
    {"q": "¿Cuántos planetas hay en el sistema solar?", "a": "8", "opts": ["7", "8", "9", "10"]},
    {"q": "¿Cuál es el elemento químico del oro?", "a": "Au", "opts": ["Go", "Or", "Au", "Ag"]},
    {"q": "¿Quién pintó la Mona Lisa?", "a": "Leonardo da Vinci", "opts": ["Picasso", "Monet", "Leonardo da Vinci", "Van Gogh"]},
    {"q": "¿Cuál es la capital de Japón?", "a": "Tokio", "opts": ["Osaka", "Tokio", "Kioto", "Hiroshima"]},
    {"q": "¿Cuántos huesos tiene el cuerpo humano adulto?", "a": "206", "opts": ["189", "206", "215", "224"]},
    {"q": "¿Cuál es el río más largo del mundo?", "a": "Nilo", "opts": ["Amazonas", "Yangtsé", "Nilo", "Misisipi"]},
    {"q": "¿En qué continente está Egipto?", "a": "África", "opts": ["Asia", "África", "Europa", "Medio Oriente"]},
    {"q": "¿Cuántos colores tiene el arcoíris?", "a": "7", "opts": ["5", "6", "7", "8"]},
]

XP_PER_MESSAGE = 15
XP_COOLDOWN_SECONDS = 60

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="n!", intents=intents, help_command=None)
tree = bot.tree

xp_cooldowns: dict[str, datetime] = {}
music_queues: dict[int, list] = {}
music_players: dict[int, discord.VoiceClient] = {}


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT,
                guild_id TEXT,
                username TEXT,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 0,
                messages INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id TEXT PRIMARY KEY,
                prefix TEXT DEFAULT 'n!',
                welcome_channel TEXT,
                welcome_message TEXT DEFAULT 'Bienvenido/a {user} al servidor {server}!',
                log_channel TEXT,
                xp_enabled INTEGER DEFAULT 1,
                mod_role TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mod_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                action TEXT,
                moderator_id TEXT,
                moderator_name TEXT,
                target_id TEXT,
                target_name TEXT,
                reason TEXT,
                timestamp TEXT
            )
        """)
        await db.commit()


async def get_user_data(user_id: str, guild_id: str, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, guild_id, username) VALUES (?, ?, ?)",
            (user_id, guild_id, username)
        )
        await db.commit()
        async with db.execute(
            "SELECT xp, level, messages FROM users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        ) as cur:
            return await cur.fetchone()


async def get_guild_settings(guild_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (guild_id,)
        )
        await db.commit()
        async with db.execute(
            "SELECT prefix, welcome_channel, welcome_message, log_channel, xp_enabled, mod_role FROM guild_settings WHERE guild_id = ?",
            (guild_id,)
        ) as cur:
            return await cur.fetchone()


async def update_guild_setting(guild_id: str, key: str, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE guild_settings SET {key} = ? WHERE guild_id = ?", (value, guild_id)
        )
        await db.commit()


async def add_xp(user_id: str, guild_id: str, username: str, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET xp = xp + ?, messages = messages + 1 WHERE user_id = ? AND guild_id = ?",
            (amount, user_id, guild_id)
        )
        await db.commit()
        async with db.execute(
            "SELECT xp, level FROM users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        ) as cur:
            row = await cur.fetchone()
    return row


def xp_for_level(level: int) -> int:
    return 100 * (level + 1) * (level + 2) // 2


async def check_levelup(user_id: str, guild_id: str, xp: int, level: int):
    needed = xp_for_level(level)
    if xp >= needed:
        new_level = level + 1
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET level = ? WHERE user_id = ? AND guild_id = ?",
                (new_level, user_id, guild_id)
            )
            await db.commit()
        return new_level
    return None


async def log_mod_action(guild_id, action, mod_id, mod_name, target_id, target_name, reason):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO mod_logs (guild_id, action, moderator_id, moderator_name, target_id, target_name, reason, timestamp) VALUES (?,?,?,?,?,?,?,?)",
            (guild_id, action, mod_id, mod_name, target_id, target_name, reason, datetime.utcnow().isoformat())
        )
        await db.commit()


@bot.event
async def on_ready():
    await init_db()
    await tree.sync()
    print(f"Neko Bot conectado como {bot.user}")


@bot.event
async def on_member_join(member: discord.Member):
    guild_id = str(member.guild.id)
    settings = await get_guild_settings(guild_id)
    if not settings or not settings[1]:
        return
    channel = member.guild.get_channel(int(settings[1]))
    if not channel:
        return
    msg = settings[2].replace("{user}", member.mention).replace("{server}", member.guild.name)
    embed = discord.Embed(description=msg, color=0xFF69B4)
    embed.set_thumbnail(url=member.display_avatar.url)
    await channel.send(embed=embed)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    user_id = str(message.author.id)
    guild_id = str(message.guild.id)
    key = f"{user_id}:{guild_id}"
    now = datetime.utcnow()

    settings = await get_guild_settings(guild_id)
    xp_enabled = settings[4] if settings else 1

    if xp_enabled:
        last = xp_cooldowns.get(key)
        if not last or (now - last).total_seconds() >= XP_COOLDOWN_SECONDS:
            xp_cooldowns[key] = now
            await get_user_data(user_id, guild_id, message.author.name)
            gained = random.randint(10, XP_PER_MESSAGE)
            row = await add_xp(user_id, guild_id, message.author.name, gained)
            if row:
                new_level = await check_levelup(user_id, guild_id, row[0], row[1])
                if new_level:
                    embed = discord.Embed(
                        title="🎉 ¡Subiste de nivel!",
                        description=f"{message.author.mention} alcanzó el **nivel {new_level}**! ✨",
                        color=0xFF69B4
                    )
                    await message.channel.send(embed=embed)

    await bot.process_commands(message)


def social_embed(action: str, author: discord.Member, target: discord.Member | None, gif: str):
    verbs = {
        "hug": ("abraza", "un abrazo"),
        "pat": ("palmea", "palmaditas"),
        "kiss": ("besa", "un beso"),
        "slap": ("abofetea", "una bofetada"),
        "cuddle": ("acurruca con", "mimos"),
        "poke": ("pincha", "un toque"),
        "bite": ("muerde", "un mordisco"),
        "wave": ("saluda", "un saludo"),
    }
    verb, noun = verbs.get(action, (action, action))
    if target:
        desc = f"**{author.display_name}** {verb} a **{target.display_name}** y le da {noun}! 💕"
    else:
        desc = f"**{author.display_name}** quiere {noun}!"
    embed = discord.Embed(description=desc, color=0xFF69B4)
    embed.set_image(url=gif)
    return embed


def make_social_cmd(action: str):
    async def callback(interaction: discord.Interaction, usuario: discord.Member = None):
        gif = random.choice(SOCIAL_GIFS[action])
        embed = social_embed(action, interaction.user, usuario, gif)
        await interaction.response.send_message(embed=embed)
    callback.__name__ = action
    return app_commands.Command(
        name=action,
        description=f"Envía un {action} a alguien",
        callback=callback,
    )

for _action in SOCIAL_GIFS:
    tree.add_command(make_social_cmd(_action))


@tree.command(name="8ball", description="Consulta a la bola mágica neko")
@app_commands.describe(pregunta="Tu pregunta para la bola 🎱")
async def eightball(interaction: discord.Interaction, pregunta: str):
    response, positive = random.choice(EIGHTBALL_RESPONSES)
    color = 0x00FF88 if positive else 0xFF4444
    embed = discord.Embed(title="🎱 Bola Mágica Neko", color=color)
    embed.add_field(name="❓ Pregunta", value=pregunta, inline=False)
    embed.add_field(name="✨ Respuesta", value=response, inline=False)
    embed.set_thumbnail(url="https://media.tenor.com/2nt2JWsI2WIAAAAC/neko-cute.gif")
    await interaction.response.send_message(embed=embed)


@tree.command(name="nivel", description="Muestra tu nivel y XP actual")
@app_commands.describe(usuario="Usuario a consultar (opcional)")
async def nivel(interaction: discord.Interaction, usuario: discord.Member = None):
    target = usuario or interaction.user
    guild_id = str(interaction.guild_id)
    await get_user_data(str(target.id), guild_id, target.name)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT xp, level, messages FROM users WHERE user_id = ? AND guild_id = ?",
            (str(target.id), guild_id)
        ) as cur:
            row = await cur.fetchone()
    xp, level, msgs = row if row else (0, 0, 0)
    needed = xp_for_level(level)
    bar_filled = int((xp / max(needed, 1)) * 10)
    bar = "█" * bar_filled + "░" * (10 - bar_filled)
    embed = discord.Embed(title=f"📊 Nivel de {target.display_name}", color=0xFF69B4)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Nivel", value=f"**{level}**", inline=True)
    embed.add_field(name="XP", value=f"**{xp:,}** / **{needed:,}**", inline=True)
    embed.add_field(name="Mensajes", value=f"**{msgs:,}**", inline=True)
    embed.add_field(name="Progreso", value=f"`[{bar}]` {int(xp/max(needed,1)*100)}%", inline=False)
    await interaction.response.send_message(embed=embed)


@tree.command(name="ranking", description="Top 10 usuarios con más nivel en el servidor")
async def ranking(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, username, level, xp FROM users WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10",
            (guild_id,)
        ) as cur:
            rows = await cur.fetchall()
    if not rows:
        await interaction.response.send_message("Nadie tiene XP aún.", ephemeral=True)
        return
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines = []
    for i, (uid, uname, lvl, xp) in enumerate(rows):
        member = interaction.guild.get_member(int(uid))
        name = member.display_name if member else uname
        lines.append(f"{medals[i]} **{name}** — Nivel {lvl} ({xp:,} XP)")
    embed = discord.Embed(title="🏆 Ranking del Servidor", description="\n".join(lines), color=0xFFD700)
    await interaction.response.send_message(embed=embed)


@tree.command(name="trivia", description="Responde una pregunta de trivia")
async def trivia(interaction: discord.Interaction):
    q = random.choice(TRIVIA_QUESTIONS)
    opts = q["opts"][:]
    random.shuffle(opts)
    letters = ["🅰️", "🅱️", "🇨", "🇩"]
    correct_letter = None
    options_text = []
    for i, opt in enumerate(opts):
        options_text.append(f"{letters[i]} {opt}")
        if opt == q["a"]:
            correct_letter = letters[i]

    embed = discord.Embed(title="🧠 Trivia Neko", description=f"**{q['q']}**", color=0x9B59B6)
    embed.add_field(name="Opciones", value="\n".join(options_text), inline=False)
    embed.set_footer(text="¡Tienes 20 segundos para responder!")

    view = TriviaView(correct_letter, opts[opts.index(q["a"])], letters, opts)
    await interaction.response.send_message(embed=embed, view=view)


class TriviaView(discord.ui.View):
    def __init__(self, correct_letter, correct_text, letters, opts):
        super().__init__(timeout=20)
        self.correct_letter = correct_letter
        self.correct_text = correct_text
        self.answered = set()
        for i, opt in enumerate(opts):
            btn = discord.ui.Button(label=f"{letters[i]} {opt[:20]}", style=discord.ButtonStyle.secondary)
            btn.callback = self.make_callback(letters[i], opt)
            self.add_item(btn)

    def make_callback(self, letter, text):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id in self.answered:
                await interaction.response.send_message("Ya respondiste esta pregunta.", ephemeral=True)
                return
            self.answered.add(interaction.user.id)
            if letter == self.correct_letter:
                await interaction.response.send_message(f"✅ ¡Correcto! La respuesta era **{self.correct_text}**.", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ Incorrecto. La respuesta era **{self.correct_text}**.", ephemeral=True)
        return callback

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


@tree.command(name="adivinanza", description="Una adivinanza para poner a prueba tu mente")
async def adivinanza(interaction: discord.Interaction):
    riddles = [
        ("Tengo ciudades pero no casas, bosques pero no árboles, y agua pero no peces. ¿Qué soy?", "un mapa"),
        ("Cuanto más me secas, más mojada me pongo. ¿Qué soy?", "una toalla"),
        ("Vivo mientras como, muero si bebo agua. ¿Qué soy?", "el fuego"),
        ("Tengo manos pero no puedo aplaudir. ¿Qué soy?", "un reloj"),
        ("Cuanto más grande, menos puedes ver. ¿Qué soy?", "la oscuridad"),
        ("Corro pero no camino, tengo boca pero no hablo. ¿Qué soy?", "un río"),
    ]
    riddle, answer = random.choice(riddles)
    embed = discord.Embed(title="🤔 Adivinanza Neko", description=f"**{riddle}**", color=0xE67E22)
    embed.set_footer(text="Usa el botón para revelar la respuesta")

    async def reveal(inter: discord.Interaction):
        await inter.response.send_message(f"💡 La respuesta es: **{answer}**", ephemeral=True)

    view = discord.ui.View(timeout=60)
    btn = discord.ui.Button(label="💡 Revelar respuesta", style=discord.ButtonStyle.secondary)
    btn.callback = reveal
    view.add_item(btn)
    await interaction.response.send_message(embed=embed, view=view)


@tree.command(name="ban", description="Banea a un usuario del servidor")
@app_commands.describe(usuario="Usuario a banear", razon="Motivo del ban")
@app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin motivo especificado"):
    if usuario.top_role >= interaction.user.top_role:
        await interaction.response.send_message("❌ No puedes banear a alguien con igual o mayor rango.", ephemeral=True)
        return
    await usuario.ban(reason=razon)
    await log_mod_action(str(interaction.guild_id), "BAN", str(interaction.user.id), interaction.user.name,
                         str(usuario.id), usuario.name, razon)
    embed = discord.Embed(title="🔨 Usuario Baneado", color=0xFF0000)
    embed.add_field(name="Usuario", value=f"{usuario.mention} ({usuario.name})", inline=True)
    embed.add_field(name="Moderador", value=interaction.user.mention, inline=True)
    embed.add_field(name="Razón", value=razon, inline=False)
    await interaction.response.send_message(embed=embed)
    await send_mod_log(interaction.guild, embed)


@tree.command(name="kick", description="Expulsa a un usuario del servidor")
@app_commands.describe(usuario="Usuario a expulsar", razon="Motivo")
@app_commands.default_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin motivo especificado"):
    if usuario.top_role >= interaction.user.top_role:
        await interaction.response.send_message("❌ No puedes expulsar a alguien con igual o mayor rango.", ephemeral=True)
        return
    await usuario.kick(reason=razon)
    await log_mod_action(str(interaction.guild_id), "KICK", str(interaction.user.id), interaction.user.name,
                         str(usuario.id), usuario.name, razon)
    embed = discord.Embed(title="👢 Usuario Expulsado", color=0xFF8800)
    embed.add_field(name="Usuario", value=f"{usuario.mention} ({usuario.name})", inline=True)
    embed.add_field(name="Moderador", value=interaction.user.mention, inline=True)
    embed.add_field(name="Razón", value=razon, inline=False)
    await interaction.response.send_message(embed=embed)
    await send_mod_log(interaction.guild, embed)


@tree.command(name="mute", description="Silencia a un usuario por un tiempo determinado")
@app_commands.describe(usuario="Usuario a silenciar", minutos="Duración en minutos", razon="Motivo")
@app_commands.default_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, usuario: discord.Member, minutos: int = 10, razon: str = "Sin motivo"):
    if usuario.top_role >= interaction.user.top_role:
        await interaction.response.send_message("❌ No puedes silenciar a alguien con igual o mayor rango.", ephemeral=True)
        return
    duration = timedelta(minutes=minutos)
    await usuario.timeout(duration, reason=razon)
    await log_mod_action(str(interaction.guild_id), "MUTE", str(interaction.user.id), interaction.user.name,
                         str(usuario.id), usuario.name, razon)
    embed = discord.Embed(title="🔇 Usuario Silenciado", color=0xFFA500)
    embed.add_field(name="Usuario", value=f"{usuario.mention}", inline=True)
    embed.add_field(name="Duración", value=f"**{minutos}** minutos", inline=True)
    embed.add_field(name="Razón", value=razon, inline=False)
    await interaction.response.send_message(embed=embed)
    await send_mod_log(interaction.guild, embed)


@tree.command(name="unmute", description="Quita el silencio a un usuario")
@app_commands.default_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, usuario: discord.Member):
    await usuario.timeout(None)
    embed = discord.Embed(title="🔊 Usuario Des-silenciado", color=0x00FF88)
    embed.description = f"{usuario.mention} ya puede hablar de nuevo."
    await interaction.response.send_message(embed=embed)


@tree.command(name="warn", description="Advierte a un usuario")
@app_commands.default_permissions(manage_messages=True)
async def warn(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin motivo"):
    await log_mod_action(str(interaction.guild_id), "WARN", str(interaction.user.id), interaction.user.name,
                         str(usuario.id), usuario.name, razon)
    embed = discord.Embed(title="⚠️ Advertencia", color=0xFFFF00)
    embed.add_field(name="Usuario", value=usuario.mention, inline=True)
    embed.add_field(name="Razón", value=razon, inline=False)
    await interaction.response.send_message(embed=embed)
    await send_mod_log(interaction.guild, embed)


@tree.command(name="clear", description="Borra mensajes del canal")
@app_commands.describe(cantidad="Número de mensajes a borrar (máx 100)")
@app_commands.default_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, cantidad: int):
    if cantidad < 1 or cantidad > 100:
        await interaction.response.send_message("❌ Entre 1 y 100 mensajes.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=cantidad)
    await interaction.followup.send(f"✅ Se borraron **{len(deleted)}** mensajes.", ephemeral=True)


async def send_mod_log(guild: discord.Guild, embed: discord.Embed):
    settings = await get_guild_settings(str(guild.id))
    if not settings or not settings[3]:
        return
    channel = guild.get_channel(int(settings[3]))
    if channel:
        await channel.send(embed=embed)


@tree.command(name="config", description="Configura ajustes del bot para este servidor")
@app_commands.describe(ajuste="Qué configurar", valor="Nuevo valor")
@app_commands.choices(ajuste=[
    app_commands.Choice(name="Prefijo", value="prefix"),
    app_commands.Choice(name="Canal de bienvenida (ID)", value="welcome_channel"),
    app_commands.Choice(name="Mensaje de bienvenida", value="welcome_message"),
    app_commands.Choice(name="Canal de logs (ID)", value="log_channel"),
    app_commands.Choice(name="XP activado (1=sí, 0=no)", value="xp_enabled"),
])
@app_commands.default_permissions(administrator=True)
async def config(interaction: discord.Interaction, ajuste: str, valor: str):
    guild_id = str(interaction.guild_id)
    await get_guild_settings(guild_id)
    if ajuste == "xp_enabled":
        valor_db = int(valor) if valor in ("0", "1") else 1
    else:
        valor_db = valor
    await update_guild_setting(guild_id, ajuste, valor_db)
    embed = discord.Embed(title="⚙️ Configuración Actualizada", color=0x00FF88)
    embed.add_field(name=ajuste, value=f"→ `{valor}`", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="serverinfo", description="Información del servidor")
async def serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    embed = discord.Embed(title=g.name, color=0xFF69B4)
    embed.set_thumbnail(url=g.icon.url if g.icon else None)
    embed.add_field(name="👑 Dueño", value=f"<@{g.owner_id}>", inline=True)
    embed.add_field(name="👥 Miembros", value=f"**{g.member_count}**", inline=True)
    embed.add_field(name="📅 Creado", value=g.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="💬 Canales", value=f"**{len(g.text_channels)}** texto / **{len(g.voice_channels)}** voz", inline=True)
    embed.add_field(name="🎭 Roles", value=f"**{len(g.roles)}**", inline=True)
    embed.add_field(name="😀 Emojis", value=f"**{len(g.emojis)}**", inline=True)
    await interaction.response.send_message(embed=embed)


@tree.command(name="userinfo", description="Información de un usuario")
async def userinfo(interaction: discord.Interaction, usuario: discord.Member = None):
    u = usuario or interaction.user
    embed = discord.Embed(title=f"{u.display_name}", color=0xFF69B4)
    embed.set_thumbnail(url=u.display_avatar.url)
    embed.add_field(name="🆔 ID", value=u.id, inline=True)
    embed.add_field(name="📅 Cuenta creada", value=u.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="📥 En servidor desde", value=u.joined_at.strftime("%d/%m/%Y") if u.joined_at else "?", inline=True)
    roles = [r.mention for r in reversed(u.roles) if r.name != "@everyone"]
    embed.add_field(name="🎭 Roles", value=" ".join(roles[:5]) or "Ninguno", inline=False)
    await interaction.response.send_message(embed=embed)


@tree.command(name="play", description="Reproduce una canción de YouTube en el canal de voz")
@app_commands.describe(busqueda="Nombre o URL de la canción")
async def play(interaction: discord.Interaction, busqueda: str):
    if not interaction.user.voice:
        await interaction.response.send_message("❌ Debes estar en un canal de voz.", ephemeral=True)
        return
    await interaction.response.defer()
    guild_id = interaction.guild_id
    vc = interaction.guild.voice_client

    if not vc:
        vc = await interaction.user.voice.channel.connect()
        music_players[guild_id] = vc

    try:
        import yt_dlp
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "noplaylist": True,
            "default_search": "ytsearch",
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(busqueda, download=False)
            if "entries" in info:
                info = info["entries"][0]
            url = info["url"]
            title = info.get("title", "Desconocido")
            duration = info.get("duration", 0)
            mins, secs = divmod(duration, 60)

        if guild_id not in music_queues:
            music_queues[guild_id] = []

        music_queues[guild_id].append({"url": url, "title": title, "duration": f"{mins}:{secs:02d}",
                                        "requester": interaction.user.display_name})

        if not vc.is_playing():
            await play_next(guild_id, vc, interaction.channel)
            embed = discord.Embed(title="🎵 Reproduciendo ahora", color=0xFF69B4)
        else:
            embed = discord.Embed(title="📋 Añadido a la cola", color=0x9B59B6)

        embed.description = f"**{title}**"
        embed.add_field(name="⏱️ Duración", value=f"{mins}:{secs:02d}", inline=True)
        embed.add_field(name="👤 Pedido por", value=interaction.user.display_name, inline=True)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error al reproducir: {str(e)[:200]}")


async def play_next(guild_id: int, vc: discord.VoiceClient, channel):
    if guild_id not in music_queues or not music_queues[guild_id]:
        return
    track = music_queues[guild_id].pop(0)
    source = discord.FFmpegPCMAudio(track["url"], **FFMPEG_OPTIONS)

    def after_play(error):
        if error:
            print(f"Error en reproducción: {error}")
        asyncio.run_coroutine_threadsafe(play_next(guild_id, vc, channel), bot.loop)

    vc.play(source, after=after_play)


@tree.command(name="skip", description="Salta la canción actual")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await interaction.response.send_message("⏭️ Canción saltada.")
    else:
        await interaction.response.send_message("❌ No hay música reproduciéndose.", ephemeral=True)


@tree.command(name="stop", description="Detiene la música y sale del canal de voz")
async def stop(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    vc = interaction.guild.voice_client
    if vc:
        music_queues[guild_id] = []
        await vc.disconnect()
        await interaction.response.send_message("⏹️ Música detenida.")
    else:
        await interaction.response.send_message("❌ No estoy en un canal de voz.", ephemeral=True)


@tree.command(name="queue", description="Muestra la cola de música")
async def queue(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    q = music_queues.get(guild_id, [])
    vc = interaction.guild.voice_client
    if not q and (not vc or not vc.is_playing()):
        await interaction.response.send_message("📋 La cola está vacía.", ephemeral=True)
        return
    lines = [f"{i+1}. **{t['title']}** ({t['duration']}) — {t['requester']}" for i, t in enumerate(q[:10])]
    embed = discord.Embed(title="🎵 Cola de Música", description="\n".join(lines) or "Vacía", color=0xFF69B4)
    await interaction.response.send_message(embed=embed)


@tree.command(name="nhelp", description="Muestra todos los comandos del Neko Bot")
async def nhelp(interaction: discord.Interaction):
    embed = discord.Embed(title="🐱 Neko Bot — Comandos", color=0xFF69B4,
                          description="Bot estilo Nekotina con todas las funciones")
    embed.add_field(name="💕 Social",
                    value="`/hug` `/pat` `/kiss` `/slap` `/cuddle` `/poke` `/bite` `/wave`\n`/8ball` `/adivinanza` `/trivia`",
                    inline=False)
    embed.add_field(name="📊 Niveles",
                    value="`/nivel` — Tu XP y nivel\n`/ranking` — Top 10 del servidor",
                    inline=False)
    embed.add_field(name="🔨 Moderación",
                    value="`/ban` `/kick` `/mute` `/unmute` `/warn` `/clear`",
                    inline=False)
    embed.add_field(name="🎵 Música",
                    value="`/play` `/skip` `/stop` `/queue`",
                    inline=False)
    embed.add_field(name="ℹ️ Info",
                    value="`/serverinfo` `/userinfo` `/config` `/nhelp`",
                    inline=False)
    embed.set_thumbnail(url="https://media.tenor.com/2nt2JWsI2WIAAAAC/neko-cute.gif")
    await interaction.response.send_message(embed=embed)


if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: Falta la variable de entorno NEKO_TOKEN")
        exit(1)
    bot.run(TOKEN)
