import discord
from discord import app_commands
import aiosqlite as _aiosqlite_real
import asyncio
import random
import re
import unicodedata
import os
from datetime import datetime, timedelta, timezone

TOKEN = os.environ.get("DISCORD_TOKEN")
# =====================================================================
#  ECONOMÍA POR SERVIDOR (infraestructura)
#  Cada servidor tiene su propio archivo de base de datos. Todo el código que
#  hace `aiosqlite.connect(DB_PATH)` usa automáticamente la base del servidor
#  donde se está ejecutando el comando (ver enter_guild más abajo).
# =====================================================================
import contextvars
import sqlite3 as _sqlite3

LEGACY_DB_PATH = "discord_bot/casino.db"            # la base vieja (economía compartida)
GLOBAL_DB_PATH = "discord_bot/global.db"            # blacklist, ajustes del panel, mapa de servidores
GUILD_DB_TEMPLATE = "discord_bot/casino_{guild_id}.db"

ADDPUNTOS_MAX = 16_666_666_666_665                  # máximo de puntos por uso de /addpuntos


class _GuildDBPath:
    """Marcador que significa 'la base de datos del servidor actual'."""

    def __repr__(self):
        return "<base de datos del servidor actual>"


DB_PATH = _GuildDBPath()

_current_guild: contextvars.ContextVar = contextvars.ContextVar("current_guild", default=None)
_guild_paths: dict = {}          # guild_id -> archivo .db
_guild_ready: set = set()        # servidores con tablas ya creadas
_guild_init_lock = None


class NoGuildContext(RuntimeError):
    """Se intentó usar la economía fuera de un servidor."""


def _resolve_db_path(database):
    if isinstance(database, _GuildDBPath):
        guild_id = _current_guild.get()
        if guild_id is None:
            raise NoGuildContext("Esta acción necesita un servidor y no se ejecutó dentro de uno.")
        path = _guild_paths.get(guild_id)
        if path is None:
            raise NoGuildContext(f"El servidor {guild_id} todavía no está preparado.")
        return path
    return database


class _AiosqliteProxy:
    """Igual que aiosqlite, pero entiende el marcador DB_PATH."""

    def connect(self, database, *args, **kwargs):
        return _aiosqlite_real.connect(_resolve_db_path(database), *args, **kwargs)

    def __getattr__(self, name):
        return getattr(_aiosqlite_real, name)


aiosqlite = _AiosqliteProxy()


class GuildView(discord.ui.View):
    """Vista que fija el servidor correcto antes de ejecutar cualquier botón o menú."""

    async def _scheduled_task(self, *args, **kwargs):
        interaction = next((a for a in args if isinstance(a, discord.Interaction)), None)
        if interaction is not None and not await _enter_interaction(interaction):
            return
        await super()._scheduled_task(*args, **kwargs)


class GuildModal(discord.ui.Modal):
    """Igual que GuildView, para formularios (modals)."""

    async def _scheduled_task(self, *args, **kwargs):
        interaction = next((a for a in args if isinstance(a, discord.Interaction)), None)
        if interaction is not None and not await _enter_interaction(interaction):
            return
        await super()._scheduled_task(*args, **kwargs)



_BASE_SHOP_ITEMS = {
    "anti_rob": {
        "name": "🛡️ Escudo Anti-Robos",
        "price": 800_000,
        "description": "Actívalo con `/use`: te protege de robos durante **1h 30m** y recibes un rol temporal que se quita solo. ¡Consumible!",
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
    "vip": {
        "name": "🎩 Rol: Casino VIP",
        "price": 3000,
        "description": "Gana **+300** 🪙 cada 12h con `/collect`.",
        "category": "rol",
        "collect_bonus": 300,
        "collect_hours": 12,
    },
    "viciado": {
        "name": "🎮 Rol: Viciado Casino",
        "price": 7000,
        "description": "Gana **+700** 🪙 cada 8h con `/collect`.",
        "category": "rol",
        "collect_bonus": 700,
        "collect_hours": 8,
    },
    "supremo": {
        "name": "👑 Rol: Casino Supremo",
        "price": 15000,
        "description": "Gana **+1,500** 🪙 cada 6h con `/collect`.",
        "category": "rol",
        "collect_bonus": 1500,
        "collect_hours": 6,
    },
    "bronce": {
        "name": "🥉 Rol: Bronce",
        "price": 50_000_000,
        "description": "Gana **+50,000,000** 🪙 cada 4h con `/collect`.",
        "category": "rol",
        "collect_bonus": 50_000_000,
        "collect_hours": 4,
    },
    "plata": {
        "name": "🥈 Rol: Plata",
        "price": 150_000_000,
        "description": "Gana **+60,000,000** 🪙 cada 5h con `/collect`.",
        "category": "rol",
        "collect_bonus": 60_000_000,
        "collect_hours": 5,
    },
    "oro": {
        "name": "🥇 Rol: Oro",
        "price": 200_000_000,
        "description": "Gana **+70,000,000** 🪙 cada 6h con `/collect`.",
        "category": "rol",
        "collect_bonus": 70_000_000,
        "collect_hours": 6,
    },
    "diamante": {
        "name": "💎 Rol: Diamante",
        "price": 250_000_000,
        "description": "Gana **+160,000,000** 🪙 cada 7h con `/collect`.",
        "category": "rol",
        "collect_bonus": 160_000_000,
        "collect_hours": 7,
    },
    "ruby": {
        "name": "🔴 Rol: Ruby",
        "price": 350_000_000,
        "description": "Gana **+200,000,000** 🪙 cada 8h con `/collect`.",
        "category": "rol",
        "collect_bonus": 200_000_000,
        "collect_hours": 8,
    },
    "esmeralda": {
        "name": "🟢 Rol: Esmeralda",
        "price": 500_000_000,
        "description": "Gana **+250,000,000** 🪙 cada 9h con `/collect`.",
        "category": "rol",
        "collect_bonus": 250_000_000,
        "collect_hours": 9,
    },
    "zafiro": {
        "name": "🔷 Rol: Zafiro",
        "price": 750_000_000,
        "description": "Gana **+350,000,000** 🪙 cada 10h con `/collect`.",
        "category": "rol",
        "collect_bonus": 350_000_000,
        "collect_hours": 10,
    },
    "obsidiana": {
        "name": "⚫ Rol: Obsidiana",
        "price": 1_000_000_000,
        "description": "Gana **+500,000,000** 🪙 cada 11h con `/collect`.",
        "category": "rol",
        "collect_bonus": 500_000_000,
        "collect_hours": 11,
    },
}

from collections.abc import Mapping as _Mapping, Sequence as _Sequence

_custom_shop: dict = {}   # servidor -> {id: objeto}: roles que los admins añadieron con /añadir rol


class _ShopMapping(_Mapping):
    """La tienda: los objetos base + los roles propios del servidor en el que se está ejecutando el comando."""

    def _all(self):
        custom = _custom_shop.get(_current_guild.get())
        return {**_BASE_SHOP_ITEMS, **custom} if custom else _BASE_SHOP_ITEMS

    def __getitem__(self, key):
        return self._all()[key]

    def __iter__(self):
        return iter(self._all())

    def __len__(self):
        return len(self._all())


class _RoleItems(_Sequence):
    """IDs de los objetos de categoría 'rol' del servidor actual."""

    def _ids(self):
        return [k for k, v in SHOP_ITEMS.items() if v["category"] == "rol"]

    def __getitem__(self, index):
        return self._ids()[index]

    def __len__(self):
        return len(self._ids())

    def __iter__(self):
        return iter(self._ids())

    def __contains__(self, item):
        return item in self._ids()


SHOP_ITEMS = _ShopMapping()
ROLE_ITEMS = _RoleItems()
ROLE_LOAN_LENDER_PERCENT = 50     # % de cada collect de un rol prestado que va para su dueño


def role_collect_payout(role_id: str, borrowed: dict) -> int:
    """Lo que recibe quien hace /collect (si el rol es prestado, descuenta el % del dueño)."""
    bonus = SHOP_ITEMS[role_id]["collect_bonus"]
    if role_id in borrowed:
        return bonus - bonus * ROLE_LOAN_LENDER_PERCENT // 100
    return bonus
LEGACY_ROLE_ITEM_IDS = {
    "role_vip": "vip",
    "role_viciado": "viciado",
    "role_supremo": "supremo",
    "role_bronce": "bronce",
    "role_plata": "plata",
    "role_oro": "oro",
    "role_diamante": "diamante",
}


def normalize_shop_item_id(item_id: str) -> str:
    item_id = item_id.strip().lower()
    return LEGACY_ROLE_ITEM_IDS.get(item_id, item_id)

FIGHTERS = {
    "novato": {
        "name": "🥊 Novato",
        "price": 5_000,
        "hp": 80, "attack": 10, "defense": 5,
        "description": "Un luchador principiante. Barato pero débil.",
    },
    "peleador": {
        "name": "⚔️ Peleador Callejero",
        "price": 50_000,
        "hp": 120, "attack": 18, "defense": 10,
        "description": "Con experiencia en las calles. Equilibrado.",
    },
    "guerrero": {
        "name": "🗡️ Guerrero",
        "price": 500_000,
        "hp": 180, "attack": 28, "defense": 18,
        "description": "Entrenado en combate cuerpo a cuerpo.",
    },
    "asesino": {
        "name": "🗡️ Asesino",
        "price": 5_000_000,
        "hp": 150, "attack": 45, "defense": 12,
        "description": "Alto daño pero poca defensa. Para arriesgados.",
    },
    "tanque": {
        "name": "🛡️ Tanque",
        "price": 10_000_000,
        "hp": 300, "attack": 20, "defense": 40,
        "description": "Casi imposible de derribar. Daño moderado.",
    },
    "campeon": {
        "name": "👑 Campeón",
        "price": 100_000_000,
        "hp": 250, "attack": 50, "defense": 35,
        "description": "El mejor luchador del casino. Ataque y defensa elite.",
    },
}

def calc_daily_reward(streak: int) -> int:
    if streak <= 1:
        return DAILY_FIRST_REWARD
    day = min(streak, 30)
    return DAILY_BASE_REWARD + (day - 2) * DAILY_STREAK_STEP

RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK_NUMBERS = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}

def evaluate_roulette_bet(numero: int, bet: str) -> tuple[bool, int, str]:
    """Returns (won, multiplier, display_name). multiplier=1→1:1, 2→2:1, 35→35:1."""
    bet = bet.lower().strip()
    # Straight-up number bet (0–36) → 35:1
    try:
        target = int(bet)
        if 0 <= target <= 36:
            num_col = "🟢" if target == 0 else ("🔴" if target in RED_NUMBERS else "⚫")
            return numero == target, 35, f"🎯 Número {num_col} {target}"
    except ValueError:
        pass
    if numero == 0:
        return False, 0, bet
    is_red  = numero in RED_NUMBERS
    is_even = numero % 2 == 0
    if bet in ("red", "rojo"):
        return is_red, 1, "🔴 Rojo"
    if bet in ("black", "negro"):
        return not is_red, 1, "⚫ Negro"
    if bet in ("even", "par", "eleven"):
        return is_even, 1, "🔵 Par (Even)"
    if bet in ("odd", "impar"):
        return not is_even, 1, "🟣 Impar (Odd)"
    if bet == "1st":
        return 1 <= numero <= 12, 2, "1️⃣ 1ra Docena (1-12)"
    if bet == "2nd":
        return 13 <= numero <= 24, 2, "2️⃣ 2da Docena (13-24)"
    if bet == "3rd":
        return 25 <= numero <= 36, 2, "3️⃣ 3ra Docena (25-36)"
    return False, 0, bet

# ───────────────────── TARJETAS DE FÚTBOL ─────────────────────────────────

CARDS_PER_PACK = 3

RARITY_CONFIG = {
    "legendario": {"emoji": "🌟", "color": 0xFFD700, "label": "LEGENDARIO", "weight": 1},
    "epico":      {"emoji": "💜", "color": 0x9B59B6, "label": "ÉPICO",      "weight": 4},
    "raro":       {"emoji": "💙", "color": 0x3498DB, "label": "RARO",       "weight": 10},
    "poco_comun": {"emoji": "💚", "color": 0x2ECC71, "label": "POCO COMÚN", "weight": 25},
    "comun":      {"emoji": "🩶", "color": 0x95A5A6, "label": "COMÚN",      "weight": 60},
}

# Cada sobre ofrece una distribución de probabilidades por carta.
# Las probabilidades de cada sobre suman 100; ninguna rareza está garantizada.
PACK_TYPES: dict[str, dict] = {
    "comun": {
        "label": "Sobre Común",       "emoji": "🩶", "price": 1_000,
        "probabilities": {
            "comun": 90, "poco_comun": 8, "raro": 1, "epico": 0.9, "legendario": 0.1,
        },
    },
    "poco_comun": {
        "label": "Sobre Poco Común",  "emoji": "💚", "price": 10_000,
        "probabilities": {
            "comun": 70, "poco_comun": 20, "raro": 8, "epico": 1.5, "legendario": 0.5,
        },
    },
    "raro": {
        "label": "Sobre Raro",        "emoji": "💙", "price": 50_000,
        "probabilities": {
            "comun": 45, "poco_comun": 30, "raro": 18, "epico": 6, "legendario": 1,
        },
    },
    "epico": {
        "label": "Sobre Épico",       "emoji": "💜", "price": 150_000,
        "probabilities": {
            "comun": 25, "poco_comun": 30, "raro": 27, "epico": 15, "legendario": 3,
        },
    },
    "legendario": {
        "label": "Sobre Legendario",  "emoji": "🌟", "price": 500_000,
        "probabilities": {
            "comun": 10, "poco_comun": 20, "raro": 30, "epico": 25, "legendario": 15,
        },
    },
}

# alias de texto → clave interna
_PACK_ALIASES: dict[str, str] = {
    "comun": "comun", "común": "comun", "c": "comun",
    "poco_comun": "poco_comun", "pococ": "poco_comun", "pc": "poco_comun",
    "poco": "poco_comun", "poco comun": "poco_comun",
    "raro": "raro", "r": "raro",
    "epico": "epico", "épico": "epico", "e": "epico",
    "legendario": "legendario", "legend": "legendario", "l": "legendario",
}

FOOTBALL_CARDS: dict[str, dict] = {
    # ─── LEGENDARIOS ──────────────────────────────────────────────────────
    "pele":        {"name": "Pelé",               "team": "Brasil",          "pos": "DEL", "ovr": 100, "rarity": "legendario"},
    "maradona":    {"name": "Diego Maradona",      "team": "Argentina",       "pos": "DEL", "ovr": 99,  "rarity": "legendario"},
    "cruyff":      {"name": "Johan Cruyff",        "team": "Países Bajos",    "pos": "DEL", "ovr": 98,  "rarity": "legendario"},
    "r9":          {"name": "Ronaldo Fenômeno",    "team": "Brasil",          "pos": "DEL", "ovr": 98,  "rarity": "legendario"},
    "zidane":      {"name": "Zinedine Zidane",     "team": "Francia",         "pos": "MC",  "ovr": 98,  "rarity": "legendario"},
    "ronaldinho":  {"name": "Ronaldinho",           "team": "Brasil",          "pos": "DEL", "ovr": 97,  "rarity": "legendario"},
    "beckenbauer": {"name": "Franz Beckenbauer",   "team": "Alemania",        "pos": "DEF", "ovr": 97,  "rarity": "legendario"},
    "best":        {"name": "George Best",         "team": "Manchester Utd",  "pos": "DEL", "ovr": 96,  "rarity": "legendario"},
    # ─── ÉPICOS ────────────────────────────────────────────────────────────
    "messi":       {"name": "Lionel Messi",        "team": "Argentina",       "pos": "DEL", "ovr": 95,  "rarity": "epico"},
    "cr7":         {"name": "Cristiano Ronaldo",   "team": "Portugal",        "pos": "DEL", "ovr": 94,  "rarity": "epico"},
    "neymar":      {"name": "Neymar Jr",           "team": "Brasil",          "pos": "DEL", "ovr": 92,  "rarity": "epico"},
    "lewandowski": {"name": "R. Lewandowski",      "team": "Polonia",         "pos": "DEL", "ovr": 92,  "rarity": "epico"},
    "modric":      {"name": "Luka Modrić",         "team": "Croacia",         "pos": "MC",  "ovr": 91,  "rarity": "epico"},
    "benzema":     {"name": "Karim Benzema",       "team": "Francia",         "pos": "DEL", "ovr": 91,  "rarity": "epico"},
    "bellingham":  {"name": "Jude Bellingham",     "team": "Real Madrid",     "pos": "MC",  "ovr": 90,  "rarity": "epico"},
    "buffon":      {"name": "Gianluigi Buffon",    "team": "Italia",          "pos": "POR", "ovr": 95,  "rarity": "epico"},
    "maldini":     {"name": "Paolo Maldini",       "team": "AC Milan",        "pos": "DEF", "ovr": 97,  "rarity": "epico"},
    "xavi":        {"name": "Xavi Hernández",      "team": "España",          "pos": "MC",  "ovr": 94,  "rarity": "epico"},
    # ─── RAROS ─────────────────────────────────────────────────────────────
    "mbappe":      {"name": "Kylian Mbappé",       "team": "Francia",         "pos": "DEL", "ovr": 92,  "rarity": "raro"},
    "haaland":     {"name": "Erling Haaland",      "team": "Noruega",         "pos": "DEL", "ovr": 91,  "rarity": "raro"},
    "debruyne":    {"name": "Kevin De Bruyne",     "team": "Bélgica",         "pos": "MC",  "ovr": 91,  "rarity": "raro"},
    "salah":       {"name": "Mohamed Salah",       "team": "Egipto",          "pos": "DEL", "ovr": 90,  "rarity": "raro"},
    "vvd":         {"name": "Virgil van Dijk",     "team": "Países Bajos",    "pos": "DEF", "ovr": 90,  "rarity": "raro"},
    "neuer":       {"name": "Manuel Neuer",        "team": "Alemania",        "pos": "POR", "ovr": 90,  "rarity": "raro"},
    "courtois":    {"name": "Thibaut Courtois",    "team": "Bélgica",         "pos": "POR", "ovr": 90,  "rarity": "raro"},
    "son":         {"name": "Heung-min Son",       "team": "Corea del Sur",   "pos": "DEL", "ovr": 89,  "rarity": "raro"},
    "kane":        {"name": "Harry Kane",          "team": "Inglaterra",      "pos": "DEL", "ovr": 89,  "rarity": "raro"},
    "vinijr":      {"name": "Vinicius Jr",         "team": "Brasil",          "pos": "DEL", "ovr": 89,  "rarity": "raro"},
    "iniesta":     {"name": "Andrés Iniesta",      "team": "España",          "pos": "MC",  "ovr": 93,  "rarity": "raro"},
    "kaka":        {"name": "Kaká",                "team": "Brasil",          "pos": "MC",  "ovr": 93,  "rarity": "raro"},
    # ─── POCO COMUNES ──────────────────────────────────────────────────────
    "griezmann":   {"name": "Antoine Griezmann",   "team": "Francia",         "pos": "DEL", "ovr": 87,  "rarity": "poco_comun"},
    "casemiro":    {"name": "Casemiro",            "team": "Brasil",          "pos": "MC",  "ovr": 87,  "rarity": "poco_comun"},
    "brunof":      {"name": "Bruno Fernandes",     "team": "Portugal",        "pos": "MC",  "ovr": 87,  "rarity": "poco_comun"},
    "pedri":       {"name": "Pedri",               "team": "España",          "pos": "MC",  "ovr": 87,  "rarity": "poco_comun"},
    "gavi":        {"name": "Gavi",                "team": "España",          "pos": "MC",  "ovr": 86,  "rarity": "poco_comun"},
    "saka":        {"name": "Bukayo Saka",         "team": "Inglaterra",      "pos": "DEL", "ovr": 86,  "rarity": "poco_comun"},
    "rodri":       {"name": "Rodri",               "team": "España",          "pos": "MC",  "ovr": 88,  "rarity": "poco_comun"},
    "declanrice":  {"name": "Declan Rice",         "team": "Inglaterra",      "pos": "MC",  "ovr": 85,  "rarity": "poco_comun"},
    "alisson":     {"name": "Alisson Becker",      "team": "Brasil",          "pos": "POR", "ovr": 89,  "rarity": "poco_comun"},
    "oblak":       {"name": "Jan Oblak",           "team": "Eslovenia",       "pos": "POR", "ovr": 88,  "rarity": "poco_comun"},
    "rudiger":     {"name": "Antonio Rüdiger",     "team": "Alemania",        "pos": "DEF", "ovr": 85,  "rarity": "poco_comun"},
    "camavinga":   {"name": "Eduardo Camavinga",   "team": "Francia",         "pos": "MC",  "ovr": 84,  "rarity": "poco_comun"},
    "yamal":       {"name": "Lamine Yamal",        "team": "España",          "pos": "DEL", "ovr": 87,  "rarity": "poco_comun"},
    "valverde":    {"name": "Federico Valverde",   "team": "Uruguay",         "pos": "MC",  "ovr": 87,  "rarity": "poco_comun"},
    # ─── COMUNES ───────────────────────────────────────────────────────────
    "rashford":    {"name": "Marcus Rashford",     "team": "Inglaterra",      "pos": "DEL", "ovr": 82,  "rarity": "comun"},
    "carvajal":    {"name": "Dani Carvajal",       "team": "España",          "pos": "DEF", "ovr": 83,  "rarity": "comun"},
    "mendy":       {"name": "Ferland Mendy",       "team": "Francia",         "pos": "DEF", "ovr": 82,  "rarity": "comun"},
    "tchouameni":  {"name": "A. Tchouaméni",       "team": "Francia",         "pos": "MC",  "ovr": 84,  "rarity": "comun"},
    "luisdiaz":    {"name": "Luis Díaz",           "team": "Colombia",        "pos": "DEL", "ovr": 84,  "rarity": "comun"},
    "nunez":       {"name": "Darwin Núñez",        "team": "Uruguay",         "pos": "DEL", "ovr": 82,  "rarity": "comun"},
    "emimartinez": {"name": "Emiliano Martínez",   "team": "Argentina",       "pos": "POR", "ovr": 85,  "rarity": "comun"},
    "thuram":      {"name": "Marcus Thuram",       "team": "Francia",         "pos": "DEL", "ovr": 83,  "rarity": "comun"},
    "dembele":     {"name": "Ousmane Dembélé",     "team": "Francia",         "pos": "DEL", "ovr": 83,  "rarity": "comun"},
    "goretzka":    {"name": "Leon Goretzka",       "team": "Alemania",        "pos": "MC",  "ovr": 83,  "rarity": "comun"},
    "stones":      {"name": "John Stones",         "team": "Inglaterra",      "pos": "DEF", "ovr": 83,  "rarity": "comun"},
    "robertson":   {"name": "Andy Robertson",     "team": "Escocia",         "pos": "DEF", "ovr": 84,  "rarity": "comun"},
    "trippier":    {"name": "Kieran Trippier",     "team": "Inglaterra",      "pos": "DEF", "ovr": 83,  "rarity": "comun"},
    "dimarco":     {"name": "Federico Dimarco",    "team": "Italia",          "pos": "DEF", "ovr": 83,  "rarity": "comun"},
    "barella":     {"name": "Nicolò Barella",      "team": "Italia",          "pos": "MC",  "ovr": 85,  "rarity": "comun"},
    "depay":       {"name": "Memphis Depay",       "team": "Países Bajos",    "pos": "DEL", "ovr": 82,  "rarity": "comun"},
    "dybala":      {"name": "Paulo Dybala",        "team": "Argentina",       "pos": "DEL", "ovr": 84,  "rarity": "comun"},
    "lautaro":     {"name": "Lautaro Martínez",    "team": "Argentina",       "pos": "DEL", "ovr": 87,  "rarity": "comun"},
    "chiesa":      {"name": "Federico Chiesa",     "team": "Italia",          "pos": "DEL", "ovr": 83,  "rarity": "comun"},
    "havertz":     {"name": "Kai Havertz",         "team": "Alemania",        "pos": "DEL", "ovr": 84,  "rarity": "comun"},
}

# ─── índice por rareza ────────────────────────────────────────────────────
_CARD_IDS_BY_RARITY: dict[str, list[str]] = {r: [] for r in RARITY_CONFIG}
for _cid, _cdata in FOOTBALL_CARDS.items():
    _CARD_IDS_BY_RARITY[_cdata["rarity"]].append(_cid)


def _draw_from_pack(pack_key: str) -> str:
    """Draw one random card using the pack's rarity probabilities."""
    probabilities = PACK_TYPES[pack_key]["probabilities"]
    rarities = list(probabilities)
    chosen = random.choices(
        rarities,
        weights=[probabilities[rarity] for rarity in rarities],
        k=1,
    )[0]
    return random.choice(_CARD_IDS_BY_RARITY[chosen])


def _draw_pack_cards(pack_key: str) -> list[str]:
    """Draw every card independently; no rarity is guaranteed by the pack."""
    return [_draw_from_pack(pack_key) for _ in range(CARDS_PER_PACK)]


def _format_pack_probabilities(pack: dict) -> str:
    lines = []
    for rarity, probability in pack["probabilities"].items():
        config = RARITY_CONFIG[rarity]
        percentage = f"{probability:g}"
        lines.append(f"{config['emoji']} {config['label']}: **{percentage}%**")
    return "\n".join(lines)


def _card_line(card_id: str, qty: int = 1) -> str:
    c = FOOTBALL_CARDS[card_id]
    rc = RARITY_CONFIG[c["rarity"]]
    qty_str = f" x{qty}" if qty > 1 else ""
    return f"{rc['emoji']} **{c['name']}** `{c['pos']}` {c['team']} — OVR **{c['ovr']}** _{rc['label']}{qty_str}_"


async def _add_card(user_id: str, card_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO football_cards (user_id, card_id, quantity) VALUES (?,?,1) "
            "ON CONFLICT(user_id, card_id) DO UPDATE SET quantity = quantity + 1",
            (user_id, card_id)
        )
        await db.commit()


async def _remove_card(user_id: str, card_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE football_cards SET quantity = quantity - 1 WHERE user_id=? AND card_id=?",
            (user_id, card_id)
        )
        await db.execute(
            "DELETE FROM football_cards WHERE user_id=? AND card_id=? AND quantity <= 0",
            (user_id, card_id)
        )
        await db.commit()


async def _card_qty(user_id: str, card_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT quantity FROM football_cards WHERE user_id=? AND card_id=?",
            (user_id, card_id)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def _get_collection(user_id: str) -> list[tuple[str, int]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT card_id, quantity FROM football_cards WHERE user_id=? ORDER BY card_id",
            (user_id,)
        ) as cur:
            return await cur.fetchall()

# ──────────────────────────────────────────────────────────────────────────

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
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

PREFIX = ","
SHOP_ROLE_LOCKS: dict[tuple[int, str], asyncio.Lock] = {}


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
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
        for col in ("last_rob", "last_collect", "last_work", "last_slut", "last_crime"):
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
            except Exception:
                pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN daily_streak INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN bank INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN shield_until TEXT")
        except Exception:
            pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS fighters (
                user_id TEXT PRIMARY KEY,
                fighter_id TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS fight_cooldowns (
                user_id TEXT PRIMARY KEY,
                last_fight TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS fighter_levels (
                user_id TEXT,
                fighter_id TEXT,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                points INTEGER DEFAULT 0,
                bonus_hp INTEGER DEFAULT 0,
                bonus_attack INTEGER DEFAULT 0,
                bonus_defense INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, fighter_id)
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
        async with db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='role_collects'"
        ) as cursor:
            role_collects_table_exists = await cursor.fetchone() is not None
        await db.execute("""
            CREATE TABLE IF NOT EXISTS role_collects (
                user_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                last_collect TEXT NOT NULL,
                PRIMARY KEY (user_id, item_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shop_guild_roles (
                guild_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                role_id TEXT NOT NULL,
                PRIMARY KEY (guild_id, item_id)
            )
        """)
        for legacy_id, current_id in LEGACY_ROLE_ITEM_IDS.items():
            async with db.execute(
                "SELECT user_id, quantity FROM inventory WHERE item_id=?",
                (legacy_id,),
            ) as cursor:
                old_inventory_rows = await cursor.fetchall()
            for user_id, quantity in old_inventory_rows:
                await db.execute(
                    """
                    INSERT INTO inventory (user_id, item_id, quantity) VALUES (?, ?, ?)
                    ON CONFLICT(user_id, item_id)
                    DO UPDATE SET quantity = inventory.quantity + excluded.quantity
                    """,
                    (user_id, current_id, quantity),
                )
            await db.execute("DELETE FROM inventory WHERE item_id=?", (legacy_id,))

            async with db.execute(
                "SELECT user_id, last_collect FROM role_collects WHERE item_id=?",
                (legacy_id,),
            ) as cursor:
                old_collect_rows = await cursor.fetchall()
            for user_id, last_collect in old_collect_rows:
                await db.execute(
                    """
                    INSERT INTO role_collects (user_id, item_id, last_collect) VALUES (?, ?, ?)
                    ON CONFLICT(user_id, item_id)
                    DO UPDATE SET last_collect = MAX(role_collects.last_collect, excluded.last_collect)
                    """,
                    (user_id, current_id, last_collect),
                )
            await db.execute("DELETE FROM role_collects WHERE item_id=?", (legacy_id,))

        if not role_collects_table_exists:
            role_placeholders = ",".join("?" for _ in ROLE_ITEMS)
            await db.execute(
                f"""
                INSERT OR IGNORE INTO role_collects (user_id, item_id, last_collect)
                SELECT inventory.user_id, inventory.item_id, users.last_collect
                FROM inventory
                JOIN users ON users.user_id = inventory.user_id
                WHERE inventory.item_id IN ({role_placeholders})
                  AND users.last_collect IS NOT NULL
                """,
                list(ROLE_ITEMS),
            )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lottery_tickets (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                tickets INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lottery_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lottery_channels (
                guild_id TEXT PRIMARY KEY,
                channel_id TEXT
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bet_history (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   TEXT    NOT NULL,
                game      TEXT    NOT NULL,
                amount_bet INTEGER NOT NULL,
                net       INTEGER NOT NULL,
                ts        TEXT    NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS football_cards (
                user_id  TEXT NOT NULL,
                card_id  TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, card_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS card_market (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id TEXT    NOT NULL,
                card_id   TEXT    NOT NULL,
                price     INTEGER NOT NULL,
                ts        TEXT    NOT NULL
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


async def log_bet(user_id: str, game: str, amount_bet: int, net: int):
    """Record a completed bet in bet_history. net>0 = won, net<0 = lost."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bet_history (user_id, game, amount_bet, net, ts) VALUES (?,?,?,?,?)",
            (user_id, game, amount_bet, net, datetime.utcnow().isoformat())
        )
        await db.commit()


async def get_bank(user_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT bank FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def send_prefix_balance(message: discord.Message, args: list[str]):
    target = message.author
    if args:
        if message.guild is None:
            await message.channel.send("❌ Para consultar a otra persona, usa el comando dentro de un servidor.")
            return

        target_text = " ".join(args).strip()
        match = re.fullmatch(r"<@!?(\d+)>|(\d+)", target_text)
        if match:
            target_id = int(match.group(1) or match.group(2))
            target = message.guild.get_member(target_id)
            if target is None:
                try:
                    target = await message.guild.fetch_member(target_id)
                except (discord.NotFound, discord.HTTPException):
                    target = None
        else:
            username = target_text.removeprefix("@").casefold()
            matches = {
                member.id: member
                for member in getattr(message.guild, "members", [])
                if username in {
                    getattr(member, "name", "").casefold(),
                    getattr(member, "display_name", "").casefold(),
                }
            }
            if len(matches) == 1:
                target = next(iter(matches.values()))
            elif len(matches) > 1:
                await message.channel.send("❌ Hay varios usuarios con ese nombre. Menciónalo o usa su ID.")
                return
            else:
                target = None

        if target is None:
            await message.channel.send(
                "❌ No encontré a ese usuario. Prueba `,bal @usuario` o `,bal ID`."
            )
            return

    target_id = str(target.id)
    if target_id == str(message.author.id):
        await get_or_create_user(target_id, target.name)
    bal = await get_balance(target_id)
    bank_bal = await get_bank(target_id)
    total = bal + bank_bal
    target_name = getattr(target, "display_name", target.name)
    embed = discord.Embed(title=f"💰 Saldo de {target_name}", color=0xFFD700)
    embed.add_field(name="👛 Cartera", value=f"**{bal:,}** 🪙", inline=True)
    embed.add_field(name="🏦 Banco", value=f"**{bank_bal:,}** 🪙", inline=True)
    embed.add_field(name="📊 Total", value=f"**{total:,}** 🪙", inline=True)
    embed.set_footer(text=f"Casino Bot • Consultado por {message.author.name}")
    await message.channel.send(embed=embed)


MAX_BALANCE = 1_000_000_000_000_000


async def update_bank(user_id: str, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET bank = MIN(bank + ?, ?) WHERE user_id = ?", (amount, MAX_BALANCE, user_id))
        await db.commit()


async def update_balance(user_id: str, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = MIN(balance + ?, ?) WHERE user_id = ?", (amount, MAX_BALANCE, user_id))
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


async def add_to_inventory(user_id: str, item_id: str, quantity: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO inventory (user_id, item_id, quantity) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, item_id) DO UPDATE SET quantity = quantity + excluded.quantity",
            (user_id, item_id, quantity)
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


async def collect_available_role_earnings(
    user_id: str,
    now: datetime | None = None,
) -> tuple[list[str], list[str], list[tuple[str, datetime]], dict[str, str], dict[str, int], int]:
    """Collect only roles whose individual cooldown has expired.

    Incluye los roles que le prestaron (el dueño recibe su %), excluye los que el
    usuario prestó y aplica el evento de collect doble.
    Devuelve (owned, ready, waiting, borrowed, payouts, multiplier) con
    borrowed = {role_id: lender_id} y payouts = {role_id: monedas que recibe}.
    """
    role_placeholders = ",".join("?" for _ in ROLE_ITEMS)
    now = now or datetime.utcnow()
    owned_roles: list[str] = []
    ready_roles: list[str] = []
    waiting_roles: list[tuple[str, datetime]] = []
    payouts: dict[str, int] = {}
    multiplier = 1
    borrowed: dict[str, str] = {}

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute(
            f"SELECT item_id FROM inventory WHERE user_id=? AND quantity > 0 "
            f"AND item_id IN ({role_placeholders})",
            (user_id, *ROLE_ITEMS),
        ) as cursor:
            inventory_roles = [row[0] for row in await cursor.fetchall()]

        async with db.execute(
            "SELECT item_id FROM role_loans WHERE lender_id=? AND expires_at > ?",
            (user_id, now.isoformat()),
        ) as cursor:
            lent_out = {row[0] for row in await cursor.fetchall()}
        async with db.execute(
            "SELECT item_id, lender_id, lender_percent FROM role_loans WHERE borrower_id=? AND expires_at > ?",
            (user_id, now.isoformat()),
        ) as cursor:
            borrowed_info = {row[0]: (row[1], row[2]) for row in await cursor.fetchall()}

        owned_roles = [r for r in inventory_roles if r not in lent_out]
        for role_id in list(borrowed_info):
            if role_id in owned_roles:
                del borrowed_info[role_id]  # ya lo compró: cobra completo
            else:
                owned_roles.append(role_id)
        borrowed = {r: info[0] for r, info in borrowed_info.items()}

        if not owned_roles:
            await db.commit()
            return [], [], [], {}, {}, 1

        multiplier = await _collect_multiplier(db, now)

        async with db.execute(
            "SELECT item_id, last_collect FROM role_collects WHERE user_id=?",
            (user_id,),
        ) as cursor:
            last_collect_by_role = dict(await cursor.fetchall())

        for role_id in owned_roles:
            last_collect = last_collect_by_role.get(role_id)
            cooldown = timedelta(hours=SHOP_ITEMS[role_id]["collect_hours"])
            if not last_collect or now - datetime.fromisoformat(last_collect) >= cooldown:
                ready_roles.append(role_id)
            else:
                next_collect = datetime.fromisoformat(last_collect) + cooldown
                waiting_roles.append((role_id, next_collect))

        if ready_roles:
            total_bonus = 0
            for role_id in ready_roles:
                base = SHOP_ITEMS[role_id]["collect_bonus"] * multiplier
                if role_id in borrowed_info:
                    lender_id, pct = borrowed_info[role_id]
                    lender_share = base * pct // 100
                    payouts[role_id] = base - lender_share
                    if lender_share:
                        await db.execute(
                            "UPDATE users SET balance=MIN(balance + ?, ?) WHERE user_id=?",
                            (lender_share, MAX_BALANCE, lender_id),
                        )
                        await db.execute(
                            "UPDATE role_loans SET earned = earned + ? WHERE lender_id=? AND item_id=?",
                            (lender_share, lender_id, role_id),
                        )
                else:
                    payouts[role_id] = base
                total_bonus += payouts[role_id]
                await db.execute(
                    "INSERT INTO role_collects (user_id, item_id, last_collect) VALUES (?, ?, ?) "
                    "ON CONFLICT(user_id, item_id) DO UPDATE SET last_collect=excluded.last_collect",
                    (user_id, role_id, now.isoformat()),
                )
            await db.execute(
                "UPDATE users SET balance=MIN(balance + ?, ?), last_collect=? WHERE user_id=?",
                (total_bonus, MAX_BALANCE, now.isoformat(), user_id),
            )

        await db.commit()

    if ready_roles:
        await feature_hook(user_id, "collect", len(ready_roles))
    return owned_roles, ready_roles, waiting_roles, borrowed, payouts, multiplier


async def get_role_last_collect(user_id: str, role_id: str) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT last_collect FROM role_collects WHERE user_id=? AND item_id=?",
            (user_id, role_id),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


def format_collect_wait(next_collect: datetime, now: datetime | None = None) -> str:
    remaining = max(0, int((next_collect - (now or datetime.utcnow())).total_seconds()))
    hours, remainder = divmod(remaining, 3600)
    minutes = remainder // 60
    return f"{hours}h {minutes}m"


async def get_today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


async def track_mission(user_id: str, action: str):
    await feature_hook(user_id, action)
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


LOTTERY_TICKET_PRICE = 10_000

async def run_lottery_draw():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, username, tickets FROM lottery_tickets WHERE tickets > 0") as cur:
            participants = await cur.fetchall()

    if not participants:
        return

    pool = []
    for uid, uname, tix in participants:
        pool.extend([uid] * tix)

    winner_id = random.choice(pool)
    winner_name = next(u for u, n, t in participants if u == winner_id)[1] if False else \
        next(n for u, n, t in participants if u == winner_id)
    total_tickets = sum(t for _, _, t in participants)
    pot = total_tickets * LOTTERY_TICKET_PRICE

    await update_balance(winner_id, pot)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM lottery_tickets")
        await db.execute("INSERT OR REPLACE INTO lottery_meta (key, value) VALUES ('last_draw', ?)",
                         (datetime.utcnow().isoformat(),))
        await db.commit()

    embed = discord.Embed(title="🎰 ¡SORTEO DE LOTERÍA!", color=0xFFD700)
    embed.description = (
        f"🏆 **¡<@{winner_id}> gana la lotería!**\n\n"
        f"💰 Premio: **{pot:,}** 🪙\n"
        f"🎟️ Boletos vendidos: **{total_tickets:,}**\n"
        f"👥 Participantes: **{len(participants)}**\n\n"
        f"_El próximo sorteo es en **7 días**. Usa `,lottery` para participar._"
    )

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT channel_id FROM lottery_channels") as cur:
            channels = await cur.fetchall()

    for (ch_id,) in channels:
        ch = client.get_channel(int(ch_id))
        if ch:
            try:
                await ch.send(embed=embed)
            except Exception:
                pass


async def _lottery_tick():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM lottery_meta WHERE key = 'last_draw'") as cur:
            row = await cur.fetchone()
            last_draw = row[0] if row else None

    now = datetime.utcnow()
    if last_draw is None:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO lottery_meta (key, value) VALUES ('last_draw', ?)",
                             (now.isoformat(),))
            await db.commit()
        return

    last_dt = datetime.fromisoformat(last_draw)
    if (now - last_dt) >= timedelta(days=7):
        await run_lottery_draw()


async def lottery_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        await asyncio.sleep(60)
        await for_each_guild(_lottery_tick)

@client.event
async def on_ready():
    global _background_started
    await init_global_db()
    await load_blacklist()
    await load_guild_map()
    await run_economy_migration()
    for guild in list(client.guilds):
        try:
            await enter_guild(guild.id)
        except Exception as exc:
            print(f"No pude preparar el servidor {guild.id}: {exc}")
    await config_load()
    await tree.sync()
    if not _background_started:
        _background_started = True
        asyncio.create_task(lottery_loop())
        asyncio.create_task(shield_role_loop())
        asyncio.create_task(_loan_loop())
        asyncio.create_task(role_loan_loop())
        asyncio.create_task(weekly_loop())
        asyncio.create_task(dashboard_start())
    print(f"Bot conectado como {client.user} (ID público: {client.user.id})")


@tree.command(name="balance", description="Muestra tu saldo actual")
async def balance(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    row = await get_or_create_user(user_id, interaction.user.name)
    bank_bal = await get_bank(user_id)
    wallet = row[0]
    total = wallet + bank_bal
    embed = discord.Embed(title="💰 Tu Saldo", color=0xFFD700)
    embed.add_field(name="👛 Cartera", value=f"**{wallet:,}** 🪙", inline=True)
    embed.add_field(name="🏦 Banco", value=f"**{bank_bal:,}** 🪙", inline=True)
    embed.add_field(name="📊 Total", value=f"**{total:,}** 🪙", inline=True)
    embed.set_footer(text=f"Casino Bot • {interaction.user.name} • El banco es seguro contra robos")
    await interaction.response.send_message(embed=embed)


@tree.command(name="daily", description="Recoge tu recompensa diaria con racha de días")
async def daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    row = await get_or_create_user(user_id, interaction.user.name)
    last_daily = row[1]
    now = datetime.utcnow()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT daily_streak FROM users WHERE user_id = ?", (user_id,)) as cur:
            srow = await cur.fetchone()
            current_streak = (srow[0] or 0) if srow else 0

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
        new_streak = (current_streak + 1) if diff < timedelta(hours=48) else 1
    else:
        new_streak = 1

    if new_streak > 30:
        new_streak = 1

    reward = calc_daily_reward(new_streak)
    next_reward = calc_daily_reward(min(new_streak + 1, 30))

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ?, last_daily = ?, daily_streak = ? WHERE user_id = ?",
            (reward, now.isoformat(), new_streak, user_id)
        )
        await db.commit()

    bal = await get_balance(user_id)
    streak_bar = "🔥" * min(new_streak, 10) + ("+" if new_streak > 10 else "")
    embed = discord.Embed(title="🎁 ¡Recompensa Diaria!", color=0x00FF88)
    embed.description = (
        f"{streak_bar}\n"
        f"**Día {new_streak}** de racha\n\n"
        f"💰 Recibiste: **{reward:,}** 🪙\n"
        f"📅 Mañana (día {min(new_streak+1,30)}): **{next_reward:,}** 🪙\n\n"
        f"👛 Saldo actual: **{bal:,}** 🪙"
    )
    await track_mission(user_id, "daily_used")
    await interaction.response.send_message(embed=embed)


@tree.command(name="collect", description="Recoge ganancias de tus roles de casino")
async def collect(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)
    owned_roles, ready_roles, waiting_roles, borrowed, payouts, multiplier = await collect_available_role_earnings(user_id)

    if not owned_roles:
        embed = discord.Embed(title="❌ Sin Roles", color=0xFF4444)
        embed.description = (
            "No tienes ningún rol activo.\n"
            "Compra un rol desde `/buy` para ganar monedas con `/collect`.\n\n"
            "🥉 **Bronce** — +50,000,000 🪙 cada 4h\n"
            "🥈 **Plata** — +60,000,000 🪙 cada 5h\n"
            "🥇 **Oro** — +70,000,000 🪙 cada 6h\n"
            "💎 **Diamante** — +160,000,000 🪙 cada 7h\n"
            "🔴 **Ruby** — +200,000,000 🪙 cada 8h\n"
            "🟢 **Esmeralda** — +250,000,000 🪙 cada 9h\n"
            "🔷 **Zafiro** — +350,000,000 🪙 cada 10h\n"
            "⚫ **Obsidiana** — +500,000,000 🪙 cada 11h"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if not ready_roles:
        embed = discord.Embed(title="⏰ Ningún collect listo todavía", color=0xFFAA00)
        embed.description = "\n".join(
            f"{SHOP_ITEMS[role_id]['name']}: vuelve en **{format_collect_wait(next_collect)}**"
            for role_id, next_collect in waiting_roles
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    total_bonus = sum(payouts[r] for r in ready_roles)

    event_note = f" · 🎉 evento x{multiplier}" if multiplier > 1 else ""
    new_balance = await get_balance(user_id)
    embed = discord.Embed(title="💰 ¡Ganancias Recogidas!", color=0x00FF88)
    lines = "\n".join(
        f"{SHOP_ITEMS[r]['name']}{f' (prestado · {ROLE_LOAN_LENDER_PERCENT}% para su dueño)' if r in borrowed else ''} "
        f"→ +**{payouts[r]:,}** 🪙"
        for r in ready_roles
    )
    embed.description = (
        f"{lines}\n\n"
        f"**Total:** +**{total_bonus:,}** 🪙{event_note}\n"
        f"Saldo actual: **{new_balance:,}** 🪙"
    )
    if waiting_roles:
        embed.add_field(
            name="⏳ Aún en espera",
            value="\n".join(
                f"{SHOP_ITEMS[role_id]['name']}: **{format_collect_wait(next_collect)}**"
                for role_id, next_collect in waiting_roles
            ),
            inline=False,
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


@tree.command(name="dep", description="Deposita monedas en el banco (seguras contra robos)")
@app_commands.describe(cantidad="Cantidad a depositar, o escribe 'all' para depositar todo")
async def dep(interaction: discord.Interaction, cantidad: str):
    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)
    wallet = await get_balance(user_id)

    if cantidad.lower() == "all":
        amount = wallet
    else:
        try:
            amount = int(cantidad)
        except ValueError:
            await interaction.response.send_message("❌ Escribe un número o `all`.", ephemeral=True)
            return

    if amount <= 0:
        await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
        return
    if amount > wallet:
        embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
        embed.description = f"Solo tienes **{wallet:,}** 🪙 en cartera."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await update_balance(user_id, -amount)
    await update_bank(user_id, amount)
    new_wallet = await get_balance(user_id)
    new_bank = await get_bank(user_id)

    embed = discord.Embed(title="🏦 Depósito Exitoso", color=0x3498DB)
    embed.description = f"Depositaste **{amount:,}** 🪙 en el banco.\n"
    embed.add_field(name="👛 Cartera", value=f"**{new_wallet:,}** 🪙", inline=True)
    embed.add_field(name="🏦 Banco", value=f"**{new_bank:,}** 🪙", inline=True)
    embed.set_footer(text="El banco está protegido contra robos")
    await interaction.response.send_message(embed=embed)


@tree.command(name="withdraw", description="Retira monedas del banco a tu cartera")
@app_commands.describe(cantidad="Cantidad a retirar, o escribe 'all' para retirar todo")
async def withdraw(interaction: discord.Interaction, cantidad: str):
    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)
    bank_bal = await get_bank(user_id)

    if cantidad.lower() == "all":
        amount = bank_bal
    else:
        try:
            amount = int(cantidad)
        except ValueError:
            await interaction.response.send_message("❌ Escribe un número o `all`.", ephemeral=True)
            return

    if amount <= 0:
        await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
        return
    if amount > bank_bal:
        embed = discord.Embed(title="❌ Saldo Bancario Insuficiente", color=0xFF4444)
        embed.description = f"Solo tienes **{bank_bal:,}** 🪙 en el banco."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await update_bank(user_id, -amount)
    await update_balance(user_id, amount)
    new_wallet = await get_balance(user_id)
    new_bank = await get_bank(user_id)

    embed = discord.Embed(title="🏦 Retiro Exitoso", color=0x00FF88)
    embed.description = f"Retiraste **{amount:,}** 🪙 del banco a tu cartera.\n"
    embed.add_field(name="👛 Cartera", value=f"**{new_wallet:,}** 🪙", inline=True)
    embed.add_field(name="🏦 Banco", value=f"**{new_bank:,}** 🪙", inline=True)
    await interaction.response.send_message(embed=embed)


_ROULETTE_CHOICES = [
    app_commands.Choice(name="🔴 Rojo (1:1)",               value="rojo"),
    app_commands.Choice(name="⚫ Negro (1:1)",               value="negro"),
    app_commands.Choice(name="🔵 Par / Even (1:1)",         value="even"),
    app_commands.Choice(name="🟣 Impar / Odd (1:1)",        value="odd"),
    app_commands.Choice(name="1️⃣ 1ra Docena 1-12 (2:1)",   value="1st"),
    app_commands.Choice(name="2️⃣ 2da Docena 13-24 (2:1)",  value="2nd"),
    app_commands.Choice(name="3️⃣ 3ra Docena 25-36 (2:1)",  value="3rd"),
]


def _build_multibets_embed(resultado: int, bets: list[tuple[int, str]], bal_before: int) -> discord.Embed:
    """Build embed for multi-bet roulette result. bets = [(amount, bet_key), ...]"""
    num_emoji = "🟢" if resultado == 0 else ("🔴" if resultado in RED_NUMBERS else "⚫")
    net = 0
    lines = []
    jackpot_hit = False
    for i, (amt, bk) in enumerate(bets, 1):
        won, mult, display = evaluate_roulette_bet(resultado, bk)
        if won:
            gain = amt * mult
            net += gain
            lines.append(f"**Apuesta {i}:** {display}\n  {amt:,} 🪙 → ✅ **+{gain:,}** (x{mult})")
            if mult == 35:
                jackpot_hit = True
        else:
            net -= amt
            lines.append(f"**Apuesta {i}:** {display}\n  {amt:,} 🪙 → ❌ **-{amt:,}**")
    new_balance = bal_before + net
    net_str = f"+{net:,}" if net >= 0 else f"{net:,}"
    if jackpot_hit and net > 0:
        title, color = "🎰 ¡¡NÚMERO EXACTO!!", 0xFFD700
    elif net > 0:
        title, color = "🎰 ¡GANASTE!", 0x00FF88
    elif net == 0:
        title, color = "🎰 Empate", 0xAAAAAA
    else:
        title, color = "🎰 Perdiste...", 0xFF4444
    embed = discord.Embed(title=title, color=color)
    embed.description = (
        f"La ruleta cayó en **{num_emoji} {resultado}**\n\n"
        + "\n\n".join(lines)
        + f"\n\n{'💰' if net >= 0 else '💸'} **Balance neto:** {net_str} 🪙\n"
        f"💵 Saldo actual: **{new_balance:,}** 🪙"
    )
    return embed, net


@tree.command(name="roulette", description="Ruleta — hasta 3 apuestas en el mismo spin")
@app_commands.describe(
    cantidad="Cantidad apuesta 1",
    apuesta="Tipo apuesta 1 (color/par/impar/docena)",
    numero="Número exacto apuesta 1 (0-36) — paga 35:1",
    cantidad2="Cantidad apuesta 2 (opcional)",
    apuesta2="Tipo apuesta 2 (opcional)",
    numero2="Número exacto apuesta 2 (opcional, 0-36)",
    cantidad3="Cantidad apuesta 3 (opcional)",
    apuesta3="Tipo apuesta 3 (opcional)",
    numero3="Número exacto apuesta 3 (opcional, 0-36)",
)
@app_commands.choices(apuesta=_ROULETTE_CHOICES, apuesta2=_ROULETTE_CHOICES, apuesta3=_ROULETTE_CHOICES)
async def roulette(
    interaction: discord.Interaction,
    cantidad: int,
    apuesta: str | None = None,
    numero: int | None = None,
    cantidad2: int | None = None,
    apuesta2: str | None = None,
    numero2: int | None = None,
    cantidad3: int | None = None,
    apuesta3: str | None = None,
    numero3: int | None = None,
):
    # Build slots list from provided params
    raw_slots = [
        (cantidad,  apuesta,  numero),
        (cantidad2, apuesta2, numero2),
        (cantidad3, apuesta3, numero3),
    ]
    slots: list[tuple[int, str]] = []
    for i, (amt, ap, num) in enumerate(raw_slots, 1):
        if amt is None:
            continue
        if amt <= 0:
            await interaction.response.send_message(f"❌ La apuesta {i} debe ser mayor a 0.", ephemeral=True)
            return
        if ap is None and num is None:
            await interaction.response.send_message(
                f"❌ Apuesta {i}: elige un tipo **o** un número exacto (0-36).", ephemeral=True
            )
            return
        if num is not None and not (0 <= num <= 36):
            await interaction.response.send_message(f"❌ Apuesta {i}: el número debe estar entre 0 y 36.", ephemeral=True)
            return
        bet_key = str(num) if num is not None else ap
        slots.append((amt, bet_key))

    if not slots:
        await interaction.response.send_message("❌ Debes hacer al menos una apuesta.", ephemeral=True)
        return

    total_cost = sum(amt for amt, _ in slots)
    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)
    bal = await get_balance(user_id)

    if bal < total_cost:
        embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
        embed.description = (
            f"El total de tus apuestas es **{total_cost:,}** 🪙\n"
            f"Tienes **{bal:,}** 🪙."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    resultado = random.randint(0, 36)
    embed, net = _build_multibets_embed(resultado, slots, bal)
    await update_balance(user_id, net)
    await track_mission(user_id, "roulette_played")
    await log_bet(user_id, "🎰 Ruleta", sum(a for a, _ in slots), net)
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
    await log_bet(user_id, "🎰 Slots", cantidad, new_balance - bal)
    await interaction.response.send_message(embed=embed)


@tree.command(name="rob", description="Intenta robarle monedas a otro usuario")
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

    await interaction.response.defer()
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
        if diff < timedelta(minutes=ROB_COOLDOWN_MINUTES):
            remaining = timedelta(minutes=ROB_COOLDOWN_MINUTES) - diff
            minutes = int(remaining.total_seconds() // 60)
            seconds = int(remaining.total_seconds() % 60)
            embed = discord.Embed(title="⏰ Cooldown Activo", color=0xFF4444)
            embed.description = f"Espera **{minutes}m {seconds}s** antes de volver a intentarlo."
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

    victim_balance = await get_balance(victim_id)
    if victim_balance < 100:
        embed = discord.Embed(title="😅 Víctima Sin Fondos", color=0xFFAA00)
        embed.description = f"**{usuario.name}** tiene menos de 100 🪙. ¡No vale la pena!"
        await interaction.followup.send(embed=embed)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_rob = ? WHERE user_id = ?", (now.isoformat(), robber_id)
        )
        await db.commit()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT shield_until FROM users WHERE user_id = ?", (victim_id,)) as cur:
            srow = await cur.fetchone()
            shield_until = srow[0] if srow else None
    if shield_until:
        shield_dt = datetime.fromisoformat(shield_until)
        if datetime.utcnow() < shield_dt:
            remaining_shield = shield_dt - datetime.utcnow()
            mins_s = int(remaining_shield.total_seconds() // 60)
            embed = discord.Embed(title="🛡️ ¡Robo Bloqueado!", color=0x3498DB)
            embed.description = (
                f"**{usuario.mention}** tiene un **Escudo Anti-Robos** activo.\n"
                f"⏰ Su escudo dura **{mins_s} min** más. ¡No puedes robarle ahora!"
            )
            await interaction.followup.send(embed=embed)
            return

    success = random.random() < ROB_SUCCESS_CHANCE / 100

    if success:
        pct = random.uniform(ROB_STEAL_MIN_PCT / 100, ROB_STEAL_MAX_PCT / 100)
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
        fine = max(1, int(victim_balance * ROB_FINE_PCT / 100))
        robber_balance = await get_balance(robber_id)
        fine = min(fine, robber_balance)
        await update_balance(robber_id, -fine)
        new_robber_balance = robber_balance - fine
        jail_minutes = await jail_send(robber_id)
        embed = discord.Embed(title="🚔 ¡Te Atraparon!", color=0xFF4444)
        embed.description = (
            f"Intentaste robar a **{usuario.mention}** pero te atraparon.\n"
            f"Multa: **{fine:,}** 🪙\n\n"
            f"Tu saldo: **{new_robber_balance:,}** 🪙\n\n"
            f"🔒 **Vas a la cárcel {jail_minutes} min.** No podrás robar ni apostar. Sal antes con `/fianza`."
        )

    await interaction.followup.send(embed=embed)


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


@tree.command(name="removemoney", description="[ADMIN] Quita monedas a un usuario (pon all para quitarle todo)")
@app_commands.describe(
    usuario="Usuario objetivo",
    cantidad="Cantidad a quitar, o all para quitar todo el dinero de la cartera",
    banco="Quitar también todo lo que tiene en el banco",
)
@app_commands.default_permissions(administrator=True)
async def removemoney(interaction: discord.Interaction, usuario: discord.Member, cantidad: str, banco: bool = False):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Solo los administradores pueden usar este comando.", ephemeral=True)
        return
    result = await perform_removemoney(usuario, cantidad, banco)
    if isinstance(result, str):
        await interaction.response.send_message(result, ephemeral=True)
    else:
        await interaction.response.send_message(embed=result)


@tree.command(name="resetmoney", description="Reinicia el saldo de cartera a 0 (admins pueden resetear a otros)")
@app_commands.describe(usuario="[Solo admins] Usuario a resetear (opcional, por defecto tú mismo)")
async def resetmoney_slash(interaction: discord.Interaction, usuario: discord.Member = None):
    is_admin = interaction.user.guild_permissions.administrator
    if usuario and not is_admin:
        await interaction.response.send_message("❌ Solo los administradores pueden resetear el saldo de otros usuarios.", ephemeral=True)
        return
    target = usuario if usuario else interaction.user
    target_id = str(target.id)
    await get_or_create_user(target_id, target.name)
    cur_bal = await get_balance(target_id)
    await update_balance(target_id, -cur_bal)
    embed = discord.Embed(title="🔄 Saldo Reseteado", color=0xFF8800)
    if target.id == interaction.user.id:
        embed.description = f"Tu saldo de cartera ha sido reseteado a **0** 🪙."
    else:
        embed.description = (
            f"El saldo de {target.mention} ha sido reseteado a **0** 🪙.\n"
            f"_(Tenía **{cur_bal:,}** 🪙)_\n\n"
            f"_Por: {interaction.user.display_name}_"
        )
    await interaction.response.send_message(embed=embed)


async def send_moderation_message(interaction: discord.Interaction, content: str):
    if interaction.response.is_done():
        await interaction.followup.send(content, ephemeral=True)
    else:
        await interaction.response.send_message(content, ephemeral=True)


async def ensure_moderation_access(
    interaction: discord.Interaction,
    actor_permission: str,
    bot_permission: str,
) -> discord.Member | None:
    guild = interaction.guild
    actor = interaction.user
    if guild is None or not isinstance(actor, discord.Member):
        await send_moderation_message(interaction, "Este comando solo funciona dentro de un servidor.")
        return None

    actor_permissions = actor.guild_permissions
    actor_has_permission = (
        actor_permissions.administrator
        or getattr(actor_permissions, actor_permission, False)
    )
    if not actor_has_permission:
        permission_names = {
            "administrator": "Administrador",
            "ban_members": "Banear miembros",
            "kick_members": "Expulsar miembros",
        }
        needed = permission_names.get(actor_permission, actor_permission)
        await send_moderation_message(
            interaction,
            f"Necesitas el permiso **{needed}** para usar este comando.",
        )
        return None

    bot_member = guild.me
    if bot_member is None and client.user is not None:
        try:
            bot_member = await guild.fetch_member(client.user.id)
        except discord.HTTPException:
            bot_member = None
    if bot_member is None:
        await send_moderation_message(interaction, "No pude verificar los permisos del bot en este servidor.")
        return None

    bot_permissions = bot_member.guild_permissions
    bot_has_permission = (
        bot_permissions.administrator
        or getattr(bot_permissions, bot_permission, False)
    )
    if not bot_has_permission:
        bot_permission_names = {
            "ban_members": "Banear miembros",
            "kick_members": "Expulsar miembros",
            "moderate_members": "Moderar miembros",
            "manage_messages": "Gestionar mensajes",
            "manage_channels": "Gestionar canales",
            "manage_roles": "Gestionar roles",
        }
        needed = bot_permission_names.get(bot_permission, bot_permission)
        await send_moderation_message(
            interaction,
            f"El bot necesita el permiso **{needed}** para completar esta acción.",
        )
        return None
    return bot_member


def moderation_target_hierarchy_error(
    actor: discord.Member,
    target: discord.Member,
    bot_member: discord.Member,
    guild: discord.Guild,
) -> str | None:
    if target.id == guild.owner_id:
        return "No se puede moderar al propietario del servidor."
    if target.id == bot_member.id:
        return "El bot no puede aplicarse esta acción a sí mismo."
    if actor.id != guild.owner_id and target.top_role >= actor.top_role:
        return "No puedes moderar a alguien con un rol igual o superior al tuyo."
    if target.top_role >= bot_member.top_role:
        return "El rol más alto de esa persona debe estar por debajo del rol más alto del bot."
    return None


async def validate_moderation_target(
    interaction: discord.Interaction,
    target: discord.Member,
    bot_member: discord.Member,
) -> bool:
    actor = interaction.user
    guild = interaction.guild
    if not isinstance(actor, discord.Member) or guild is None:
        await send_moderation_message(interaction, "Este comando solo funciona dentro de un servidor.")
        return False
    error = moderation_target_hierarchy_error(actor, target, bot_member, guild)
    if error:
        await send_moderation_message(interaction, error)
        return False
    return True


@tree.command(name="ban", description="Banea a un miembro del servidor")
@app_commands.guild_only()
@app_commands.default_permissions(ban_members=True)
@app_commands.describe(usuario="Miembro que será baneado", razon="Motivo del baneo")
async def ban_command(
    interaction: discord.Interaction,
    usuario: discord.Member,
    razon: str | None = None,
):
    bot_member = await ensure_moderation_access(interaction, "ban_members", "ban_members")
    if bot_member is None or not await validate_moderation_target(interaction, usuario, bot_member):
        return
    await interaction.response.defer(ephemeral=True)
    try:
        await usuario.ban(reason=razon or f"Ban solicitado por {interaction.user}")
        await interaction.followup.send(
            f"🔨 **{usuario}** fue baneado. Motivo: {razon or 'No especificado'}.",
            ephemeral=True,
        )
    except discord.Forbidden:
        await interaction.followup.send("No tengo permisos suficientes para banear a ese miembro.", ephemeral=True)
    except discord.HTTPException:
        await interaction.followup.send("Discord no pudo completar el baneo. Inténtalo de nuevo.", ephemeral=True)


@tree.command(name="kick", description="Expulsa a un miembro del servidor")
@app_commands.guild_only()
@app_commands.default_permissions(kick_members=True)
@app_commands.describe(usuario="Miembro que será expulsado", razon="Motivo de la expulsión")
async def kick_command(
    interaction: discord.Interaction,
    usuario: discord.Member,
    razon: str | None = None,
):
    bot_member = await ensure_moderation_access(interaction, "kick_members", "kick_members")
    if bot_member is None or not await validate_moderation_target(interaction, usuario, bot_member):
        return
    await interaction.response.defer(ephemeral=True)
    try:
        await usuario.kick(reason=razon or f"Kick solicitado por {interaction.user}")
        await interaction.followup.send(
            f"👢 **{usuario}** fue expulsado. Motivo: {razon or 'No especificado'}.",
            ephemeral=True,
        )
    except discord.Forbidden:
        await interaction.followup.send("No tengo permisos suficientes para expulsar a ese miembro.", ephemeral=True)
    except discord.HTTPException:
        await interaction.followup.send("Discord no pudo completar la expulsión. Inténtalo de nuevo.", ephemeral=True)


@tree.command(name="unban", description="Quita el baneo de un usuario por su ID")
@app_commands.guild_only()
@app_commands.default_permissions(ban_members=True)
@app_commands.describe(user_id="ID de Discord del usuario", razon="Motivo para quitar el baneo")
async def unban_command(
    interaction: discord.Interaction,
    user_id: str,
    razon: str | None = None,
):
    bot_member = await ensure_moderation_access(interaction, "ban_members", "ban_members")
    if bot_member is None:
        return
    try:
        target = discord.Object(id=int(user_id))
    except ValueError:
        await send_moderation_message(interaction, "El ID debe ser un número de Discord válido.")
        return

    await interaction.response.defer(ephemeral=True)
    try:
        ban_entry = await interaction.guild.fetch_ban(target)
        await interaction.guild.unban(
            ban_entry.user,
            reason=razon or f"Unban solicitado por {interaction.user}",
        )
        await interaction.followup.send(f"✅ Se quitó el baneo de **{ban_entry.user}**.", ephemeral=True)
    except discord.NotFound:
        await interaction.followup.send("Ese usuario no está baneado en este servidor.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("No tengo permisos suficientes para quitar ese baneo.", ephemeral=True)
    except discord.HTTPException:
        await interaction.followup.send("Discord no pudo quitar el baneo. Inténtalo de nuevo.", ephemeral=True)


@tree.command(name="mute", description="Aplica timeout temporal a un miembro")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    usuario="Miembro que recibirá el timeout",
    minutos="Duración de 1 a 40320 minutos (máximo 28 días)",
    razon="Motivo del timeout",
)
async def mute_command(
    interaction: discord.Interaction,
    usuario: discord.Member,
    minutos: int,
    razon: str | None = None,
):
    bot_member = await ensure_moderation_access(interaction, "administrator", "moderate_members")
    if bot_member is None:
        return
    if not 1 <= minutos <= 40_320:
        await send_moderation_message(interaction, "La duración debe estar entre 1 y 40320 minutos (28 días).")
        return
    if not await validate_moderation_target(interaction, usuario, bot_member):
        return
    await interaction.response.defer(ephemeral=True)
    try:
        await usuario.timeout(
            timedelta(minutes=minutos),
            reason=razon or f"Timeout solicitado por {interaction.user}",
        )
        await interaction.followup.send(
            f"🔇 **{usuario}** recibió timeout durante **{minutos} minutos**.",
            ephemeral=True,
        )
    except discord.Forbidden:
        await interaction.followup.send("No puedo aplicar timeout a ese miembro.", ephemeral=True)
    except discord.HTTPException:
        await interaction.followup.send("Discord no pudo aplicar el timeout. Inténtalo de nuevo.", ephemeral=True)


@tree.command(name="unmute", description="Retira el timeout de un miembro")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.describe(usuario="Miembro al que se le retirará el timeout", razon="Motivo")
async def unmute_command(
    interaction: discord.Interaction,
    usuario: discord.Member,
    razon: str | None = None,
):
    bot_member = await ensure_moderation_access(interaction, "administrator", "moderate_members")
    if bot_member is None or not await validate_moderation_target(interaction, usuario, bot_member):
        return
    await interaction.response.defer(ephemeral=True)
    try:
        await usuario.timeout(None, reason=razon or f"Timeout retirado por {interaction.user}")
        await interaction.followup.send(f"🔊 Se retiró el timeout de **{usuario}**.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("No puedo retirar el timeout de ese miembro.", ephemeral=True)
    except discord.HTTPException:
        await interaction.followup.send("Discord no pudo retirar el timeout. Inténtalo de nuevo.", ephemeral=True)


@tree.command(name="clear", description="Borra mensajes recientes de un canal")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.describe(cantidad="Cantidad de mensajes a borrar (1 a 100)", canal="Canal de texto (por defecto, este canal)")
async def clear_command(
    interaction: discord.Interaction,
    cantidad: int,
    canal: discord.TextChannel | None = None,
):
    bot_member = await ensure_moderation_access(interaction, "administrator", "manage_messages")
    if bot_member is None:
        return
    if not 1 <= cantidad <= 100:
        await send_moderation_message(interaction, "La cantidad debe estar entre 1 y 100 mensajes.")
        return
    target_channel = canal or interaction.channel
    if not isinstance(target_channel, discord.TextChannel):
        await send_moderation_message(interaction, "Selecciona un canal de texto válido.")
        return
    await interaction.response.defer(ephemeral=True)
    try:
        deleted = await target_channel.purge(
            limit=cantidad,
            reason=f"Limpieza solicitada por {interaction.user}",
        )
        await interaction.followup.send(
            f"🧹 Se borraron **{len(deleted)}** mensajes de {target_channel.mention}.",
            ephemeral=True,
        )
    except discord.Forbidden:
        await interaction.followup.send("No tengo permisos para borrar mensajes en ese canal.", ephemeral=True)
    except discord.HTTPException:
        await interaction.followup.send(
            "Discord no pudo borrar esos mensajes. Algunos pueden ser demasiado antiguos.",
            ephemeral=True,
        )


async def set_channel_lock(
    interaction: discord.Interaction,
    canal: discord.TextChannel | None,
    locked: bool,
):
    bot_member = await ensure_moderation_access(interaction, "administrator", "manage_channels")
    if bot_member is None:
        return
    target_channel = canal or interaction.channel
    if not isinstance(target_channel, discord.TextChannel):
        await send_moderation_message(interaction, "Selecciona un canal de texto válido.")
        return

    overwrite = target_channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = False if locked else None
    await interaction.response.defer(ephemeral=True)
    try:
        await target_channel.set_permissions(
            interaction.guild.default_role,
            overwrite=overwrite,
            reason=f"Canal {'bloqueado' if locked else 'desbloqueado'} por {interaction.user}",
        )
        action = "bloqueado" if locked else "desbloqueado (permiso heredado)"
        await interaction.followup.send(f"🔒 {target_channel.mention} quedó {action}.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("No tengo permisos para cambiar los permisos de ese canal.", ephemeral=True)
    except discord.HTTPException:
        await interaction.followup.send("Discord no pudo cambiar los permisos del canal.", ephemeral=True)


@tree.command(name="lock", description="Bloquea el envío de mensajes para todos en un canal")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.describe(canal="Canal de texto (por defecto, este canal)")
async def lock_command(interaction: discord.Interaction, canal: discord.TextChannel | None = None):
    await set_channel_lock(interaction, canal, True)


@tree.command(name="unlock", description="Restablece el permiso heredado para enviar mensajes")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.describe(canal="Canal de texto (por defecto, este canal)")
async def unlock_command(interaction: discord.Interaction, canal: discord.TextChannel | None = None):
    await set_channel_lock(interaction, canal, False)


async def change_member_role(
    interaction: discord.Interaction,
    usuario: discord.Member,
    rol: discord.Role,
    razon: str | None,
    add: bool,
):
    bot_member = await ensure_moderation_access(interaction, "administrator", "manage_roles")
    if bot_member is None:
        return
    actor = interaction.user
    guild = interaction.guild
    if rol.is_default() or rol.managed:
        await send_moderation_message(interaction, "No se puede agregar o quitar ese rol.")
        return
    if actor.id != guild.owner_id and rol >= actor.top_role:
        await send_moderation_message(interaction, "El rol elegido debe estar por debajo de tu rol más alto.")
        return
    if rol >= bot_member.top_role:
        await send_moderation_message(interaction, "El rol elegido debe estar por debajo del rol más alto del bot.")
        return
    if add and rol in usuario.roles:
        await send_moderation_message(interaction, f"**{usuario}** ya tiene el rol **{rol.name}**.")
        return
    if not add and rol not in usuario.roles:
        await send_moderation_message(interaction, f"**{usuario}** no tiene el rol **{rol.name}**.")
        return

    await interaction.response.defer(ephemeral=True)
    try:
        action = "add_roles" if add else "remove_roles"
        await getattr(usuario, action)(
            rol,
            reason=razon or f"Rol {'agregado' if add else 'quitado'} por {interaction.user}",
        )
        result = "agregado a" if add else "quitado de"
        await interaction.followup.send(f"✅ El rol **{rol.name}** fue {result} **{usuario}**.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("No tengo permisos para cambiar ese rol.", ephemeral=True)
    except discord.HTTPException:
        await interaction.followup.send("Discord no pudo cambiar el rol. Inténtalo de nuevo.", ephemeral=True)


@tree.command(name="addrole", description="Agrega un rol a un miembro")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.describe(usuario="Miembro objetivo", rol="Rol que se agregará", razon="Motivo")
async def addrole_command(
    interaction: discord.Interaction,
    usuario: discord.Member,
    rol: discord.Role,
    razon: str | None = None,
):
    await change_member_role(interaction, usuario, rol, razon, True)


@tree.command(name="removerole", description="Quita un rol de un miembro")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.describe(usuario="Miembro objetivo", rol="Rol que se quitará", razon="Motivo")
async def removerole_command(
    interaction: discord.Interaction,
    usuario: discord.Member,
    rol: discord.Role,
    razon: str | None = None,
):
    await change_member_role(interaction, usuario, rol, razon, False)


def build_shop_embed(panel: bool = False) -> discord.Embed:
    embed = discord.Embed(
        title="🛍️ Tienda del Casino" if panel else "🏪 Tienda del Casino",
        color=0x9B59B6,
    )
    embed.description = (
        "Selecciona un objeto en el menú para comprarlo."
        if panel
        else "Usa `/buy` para abrir el panel de compra o `/buy <id_item>` para comprar por ID."
    )
    categories = {
        "proteccion": "🛡️ Protección",
        "rol": "👑 Roles del servidor · /use y /collect",
        "decorativo": "🎭 Decorativos",
    }
    for category, title in categories.items():
        entries = [
            (item_id, item)
            for item_id, item in SHOP_ITEMS.items()
            if item["category"] == category
        ]
        if entries:
            lines: list[str] = []
            field_number = 1
            for item_id, item in entries:
                line = (
                    f"**{item['name']}** — **{item['price']:,}** 🪙\n"
                    f"{item['description']}\n`ID: {item_id}`"
                )
                if lines and len("\n\n".join([*lines, line])) > 1024:
                    field_title = title if field_number == 1 else f"{title} (continuación)"
                    embed.add_field(name=field_title, value="\n\n".join(lines), inline=False)
                    field_number += 1
                    lines = []
                lines.append(line)
            if lines:
                field_title = title if field_number == 1 else f"{title} (continuación)"
                embed.add_field(name=field_title, value="\n\n".join(lines), inline=False)
    return embed


async def get_or_create_shop_guild_role(
    guild: discord.Guild, item_id: str
) -> discord.Role:
    lock_key = (guild.id, item_id)
    lock = SHOP_ROLE_LOCKS.setdefault(lock_key, asyncio.Lock())
    async with lock:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT role_id FROM shop_guild_roles WHERE guild_id = ? AND item_id = ?",
                (str(guild.id), item_id),
            ) as cursor:
                row = await cursor.fetchone()

        role = guild.get_role(int(row[0])) if row else None
        if role is not None:
            return role

        item_name = SHOP_ITEMS[item_id]["name"]
        role_name = item_name.split("Rol:", 1)[-1].strip()
        role = await guild.create_role(
            name=role_name,
            reason=f"Rol de tienda Vortex Casino ({item_id})",
        )

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO shop_guild_roles (guild_id, item_id, role_id)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, item_id)
                DO UPDATE SET role_id = excluded.role_id
                """,
                (str(guild.id), item_id, str(role.id)),
            )
            await db.commit()
        return role


async def grant_shop_role(
    guild: discord.Guild, member: discord.Member, item_id: str
) -> tuple[discord.Role | None, bool, str | None]:
    bot_member = guild.me
    if bot_member is None or not bot_member.guild_permissions.manage_roles:
        return None, False, "Necesito el permiso **Gestionar roles** para reclamar roles."

    role = await get_or_create_shop_guild_role(guild, item_id)
    if role >= bot_member.top_role:
        return None, False, (
            f"El rol **{role.name}** debe estar por debajo del rol más alto del bot. "
            "Pídele a un administrador que ajuste la posición de los roles."
        )
    if role in member.roles:
        return role, True, None

    await member.add_roles(
        role,
        reason=f"Rol de tienda Vortex Casino reclamado por {member}",
    )
    return role, False, None


MAX_BUY_QTY = 100
SHIELD_MINUTES = 90
_background_started = False


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[-_]+", " ", text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def resolve_shop_item(text: str) -> str | None:
    """Convierte un ID o un nombre escrito a mano en el ID real del objeto."""
    legacy = normalize_shop_item_id(text)
    if legacy in SHOP_ITEMS:
        return legacy
    t = _plain(text)
    if not t:
        return None
    for item_id, item in SHOP_ITEMS.items():
        name = _plain(item["name"])
        if t == _plain(item_id) or t == name or t == name.replace("rol ", "", 1):
            return item_id
    matches = [
        item_id for item_id, item in SHOP_ITEMS.items()
        if t in _plain(item["name"]) or t in _plain(item_id)
    ]
    return matches[0] if len(matches) == 1 else None


def parse_name_and_quantity(args: list[str]) -> tuple[int, str]:
    """',buy escudo anti robos 3' -> (3, 'escudo anti robos')."""
    args = list(args)
    qty = 1
    if len(args) > 1 and args[-1].isdigit():
        qty = int(args.pop())
    return max(1, qty), " ".join(args).strip()


async def shop_item_autocomplete(interaction: discord.Interaction, current: str):
    t = _plain(current)
    choices = []
    for item_id, item in SHOP_ITEMS.items():
        if t and t not in f"{_plain(item['name'])} {_plain(item_id)}":
            continue
        label = f"{item['name']} — {item['price']:,} 🪙"
        choices.append(app_commands.Choice(name=label[:100], value=item_id))
    return choices[:25]


async def complete_shop_purchase(
    user: discord.User | discord.Member, item_id: str, quantity: int = 1
) -> discord.Embed:
    item_data = SHOP_ITEMS[item_id]
    user_id = str(user.id)
    if item_data["category"] == "rol":
        quantity = 1  # un rol solo hace falta una vez
    quantity = max(1, min(int(quantity), MAX_BUY_QTY))
    total = item_data["price"] * quantity

    await get_or_create_user(user_id, user.name)
    balance = await get_balance(user_id)

    if balance < total:
        embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
        embed.description = (
            f"**{quantity}x {item_data['name']}** cuesta **{total:,}** 🪙 "
            f"y tienes **{balance:,}** 🪙."
        )
        return embed

    await update_balance(user_id, -total)
    await add_to_inventory(user_id, item_id, quantity)
    new_balance = await get_balance(user_id)

    embed = discord.Embed(title="🛍️ ¡Compra Exitosa!", color=0x00FF88)
    bought = f"**{quantity}x {item_data['name']}**" if quantity > 1 else f"**{item_data['name']}**"
    description = (
        f"Compraste {bought}.\n"
        f"{item_data['description']}\n\n"
        f"Gastaste: **{total:,}** 🪙\n"
        f"Saldo restante: **{new_balance:,}** 🪙"
    )
    if item_data["category"] == "rol":
        description += (
            f"\n\n💡 Usa `/use {item_id}` para reclamar el rol en este servidor. "
            "Luego usa `/collect` para cobrar sus ganancias; el objeto permanece en tu inventario."
        )
    if item_data["category"] == "proteccion":
        description += (
            f"\n\n💡 Usa `/use {item_id}` para activarlo: te protege **{SHIELD_MINUTES} min** "
            "y recibes un rol temporal que se quita solo."
        )
    embed.description = description
    return embed


# ------------------------------------------------------------------ Escudo anti-robos como rol temporal
async def init_shield_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS shield_roles (
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
            """
        )
        await db.commit()


async def activate_anti_rob(
    user: discord.User | discord.Member, guild: discord.Guild | None, remaining_before: int
) -> discord.Embed:
    """Gasta un escudo, activa la proteccion y (si se puede) asigna el rol temporal."""
    user_id = str(user.id)
    expires = datetime.utcnow() + timedelta(minutes=SHIELD_MINUTES)
    await remove_from_inventory(user_id, "anti_rob")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET shield_until = ? WHERE user_id = ?", (expires.isoformat(), user_id)
        )
        await db.commit()

    role_note = ""
    if guild is not None and isinstance(user, discord.Member):
        role = None
        error = None
        try:
            role, _already, error = await grant_shop_role(guild, user, "anti_rob")
        except discord.Forbidden:
            error = "No tengo permiso para crear o asignar roles (**Gestionar roles**)."
        except discord.HTTPException:
            error = "Discord no pudo crear o asignar el rol."
        except aiosqlite.Error:
            error = "No pude guardar el rol del servidor."

        if role is not None and not error:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    """
                    INSERT INTO shield_roles (guild_id, user_id, role_id, expires_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(guild_id, user_id)
                    DO UPDATE SET role_id = excluded.role_id, expires_at = excluded.expires_at
                    """,
                    (str(guild.id), user_id, str(role.id), expires.isoformat()),
                )
                await db.commit()
            role_note = f"\n🏷️ Rol {role.mention} asignado; se quitará solo al expirar."
        else:
            role_note = f"\n⚠️ {error} El escudo funciona igual."

    embed = discord.Embed(title="🛡️ ¡Escudo Anti-Robos Activado!", color=0x3498DB)
    embed.description = (
        f"🔒 Estás protegido de robos durante **1 hora y 30 minutos**.\n\n"
        f"⏰ Expira a las **{expires.strftime('%H:%M UTC')}**"
        f"{role_note}\n"
        f"📦 Escudos restantes: **{remaining_before - 1}**"
    )
    return embed


async def expire_shield_roles():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT guild_id, user_id, role_id, expires_at FROM shield_roles"
        ) as cur:
            rows = await cur.fetchall()

    now = datetime.utcnow()
    for guild_id, user_id, role_id, expires_at in rows:
        try:
            if datetime.fromisoformat(expires_at) > now:
                continue
        except ValueError:
            pass  # fecha corrupta: se limpia igual

        guild = client.get_guild(int(guild_id))
        if guild is not None:
            role = guild.get_role(int(role_id))
            if role is not None:
                try:
                    member = guild.get_member(int(user_id)) or await guild.fetch_member(int(user_id))
                    if role in member.roles:
                        await member.remove_roles(role, reason="Escudo Anti-Robos expirado")
                except discord.NotFound:
                    pass  # el usuario ya no esta en el servidor
                except (discord.Forbidden, discord.HTTPException) as exc:
                    print(f"No pude quitar el rol del escudo a {user_id} en {guild_id}: {exc}")

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM shield_roles WHERE guild_id = ? AND user_id = ? AND expires_at = ?",
                (guild_id, user_id, expires_at),
            )
            await db.commit()


async def shield_role_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            await for_each_guild(expire_shield_roles)
        except Exception as exc:  # el bucle nunca debe morir
            print(f"Error en shield_role_loop: {exc}")
        await asyncio.sleep(20)


# ------------------------------------------------------------------ Panel de compra con cantidad
def build_quantity_embed(item_id: str, balance: int) -> discord.Embed:
    item = SHOP_ITEMS[item_id]
    embed = discord.Embed(title="🛒 ¿Cuántos quieres comprar?", color=0x9B59B6)
    embed.description = (
        f"**{item['name']}**\n{item['description']}\n\n"
        f"💵 Precio por unidad: **{item['price']:,}** 🪙\n"
        f"👛 Tu cartera: **{balance:,}** 🪙"
    )
    if item["category"] == "rol":
        embed.set_footer(text="Los roles se compran de a 1.")
    else:
        embed.set_footer(text=f"Máximo {MAX_BUY_QTY} por compra.")
    return embed


class ShopBuySelect(discord.ui.Select):
    def __init__(self, owner_id: str):
        self.owner_id = owner_id
        options = []
        for item_id, item in SHOP_ITEMS.items():
            category = "Rol" if item["category"] == "rol" else item["category"].title()
            detail = f"{item['price']:,} monedas · {category}"
            if item["category"] == "rol":
                detail += (
                    f" · /use · +{item['collect_bonus']:,} cada "
                    f"{item['collect_hours']}h"
                )
            options.append(
                discord.SelectOption(
                    label=item["name"],
                    value=item_id,
                    description=detail[:100],
                )
            )
        super().__init__(
            placeholder="Elige un objeto para comprar",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.owner_id:
            await interaction.response.send_message(
                "Este panel pertenece a otra persona.", ephemeral=True
            )
            return
        item_id = self.values[0]
        balance = await get_balance(self.owner_id)
        await interaction.response.edit_message(
            embed=build_quantity_embed(item_id, balance),
            view=ShopQuantityView(self.owner_id, item_id),
        )


class ShopBuyView(GuildView):
    def __init__(self, owner_id: str):
        super().__init__(timeout=180)
        self.purchase_completed = False
        self.add_item(ShopBuySelect(owner_id))


class QuantityButton(discord.ui.Button):
    def __init__(self, amount: int, price: int):
        label = f"x{amount} · {price * amount:,} 🪙"
        super().__init__(label=label[:80], style=discord.ButtonStyle.success)
        self.amount = amount

    async def callback(self, interaction: discord.Interaction):
        view: ShopQuantityView = self.view
        if view.done:
            await interaction.response.send_message(
                "Esta compra ya se realizó. Abre otro panel con `/shop`.", ephemeral=True
            )
            return
        view.done = True
        result = await complete_shop_purchase(interaction.user, view.item_id, self.amount)
        await interaction.response.edit_message(embed=result, view=None)


class CustomQuantityModal(GuildModal, title="Cantidad a comprar"):
    cantidad = discord.ui.TextInput(
        label=f"¿Cuántos quieres? (1-{MAX_BUY_QTY})",
        placeholder="Ej: 12",
        min_length=1,
        max_length=4,
    )

    def __init__(self, parent_view: "ShopQuantityView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.cantidad.value.strip().replace(",", ""))
        except ValueError:
            await interaction.response.send_message("❌ Escribe un número válido.", ephemeral=True)
            return
        if not 1 <= amount <= MAX_BUY_QTY:
            await interaction.response.send_message(
                f"❌ La cantidad debe estar entre 1 y {MAX_BUY_QTY}.", ephemeral=True
            )
            return
        if self.parent_view.done:
            await interaction.response.send_message(
                "Esta compra ya se realizó. Abre otro panel con `/shop`.", ephemeral=True
            )
            return
        self.parent_view.done = True
        result = await complete_shop_purchase(interaction.user, self.parent_view.item_id, amount)
        await interaction.response.edit_message(embed=result, view=None)


class CustomQuantityButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Otra cantidad…", style=discord.ButtonStyle.primary, emoji="✏️")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CustomQuantityModal(self.view))


class BackToShopButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Volver", style=discord.ButtonStyle.secondary, emoji="↩️")

    async def callback(self, interaction: discord.Interaction):
        view: ShopQuantityView = self.view
        await interaction.response.edit_message(
            embed=build_shop_embed(panel=True), view=ShopBuyView(view.owner_id)
        )


class ShopQuantityView(GuildView):
    def __init__(self, owner_id: str, item_id: str):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.item_id = item_id
        self.done = False
        item = SHOP_ITEMS[item_id]
        amounts = [1] if item["category"] == "rol" else [1, 5, 10, 25]
        for amount in amounts:
            self.add_item(QuantityButton(amount, item["price"]))
        if item["category"] != "rol":
            self.add_item(CustomQuantityButton())
        self.add_item(BackToShopButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.owner_id:
            await interaction.response.send_message(
                "Este panel pertenece a otra persona.", ephemeral=True
            )
            return False
        return True


@tree.command(name="shop", description="Muestra los objetos disponibles en la tienda")
async def shop(interaction: discord.Interaction):
    await get_or_create_user(str(interaction.user.id), interaction.user.name)
    await interaction.response.send_message(
        embed=build_shop_embed(panel=True),
        view=ShopBuyView(str(interaction.user.id)),
        ephemeral=True,
    )


@tree.command(name="buy", description="Compra un objeto: escribe su nombre o abre el panel de compra")
@app_commands.describe(
    item="Nombre del objeto (elige de la lista); déjalo vacío para abrir el panel",
    cantidad="Cuántas unidades quieres comprar (por defecto 1)",
)
async def buy(
    interaction: discord.Interaction,
    item: str | None = None,
    cantidad: app_commands.Range[int, 1, 100] = 1,
):
    if item is None:
        await get_or_create_user(str(interaction.user.id), interaction.user.name)
        await interaction.response.send_message(
            embed=build_shop_embed(panel=True),
            view=ShopBuyView(str(interaction.user.id)),
            ephemeral=True,
        )
        return

    item_id = resolve_shop_item(item)
    if item_id is None:
        await get_or_create_user(str(interaction.user.id), interaction.user.name)
        await interaction.response.send_message(
            f"❌ No encontré **{item}**. Elige uno en el panel:",
            embed=build_shop_embed(panel=True),
            view=ShopBuyView(str(interaction.user.id)),
            ephemeral=True,
        )
        return

    embed = await complete_shop_purchase(interaction.user, item_id, cantidad)
    await interaction.response.send_message(embed=embed)


buy.autocomplete("item")(shop_item_autocomplete)


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


@tree.command(name="ranking", description="Top 10 jugadores más ricos con sus roles")
async def ranking(interaction: discord.Interaction):
    ROLE_BADGES = {
        "obsidiana": "⚫",
        "zafiro": "🔷",
        "esmeralda": "🟢",
        "ruby": "🔴",
        "diamante": "💎",
        "oro": "🥇",
        "plata": "🥈",
        "bronce": "🥉",
        "supremo": "👑",
        "viciado": "🎮",
        "vip": "🎩",
    }

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, username, balance FROM users ORDER BY balance DESC LIMIT 10"
        ) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            await interaction.response.send_message("❌ No hay usuarios registrados aún.", ephemeral=True)
            return

        user_roles: dict[str, list[str]] = {}
        for uid, _, _ in rows:
            async with db.execute(
                "SELECT item_id FROM inventory WHERE user_id = ? AND quantity > 0",
                (uid,)
            ) as cur:
                inv = await cur.fetchall()
            badges = [ROLE_BADGES[item[0]] for item in inv if item[0] in ROLE_BADGES]
            user_roles[uid] = badges

    medals = ["🥇", "🥈", "🥉"]
    embed = discord.Embed(title="🏆 Ranking del Casino", color=0xFFD700)
    description = ""
    for i, (uid, username, bal) in enumerate(rows):
        prefix = medals[i] if i < 3 else f"**#{i+1}**"
        badges_str = " ".join(user_roles.get(uid, []))
        role_part = f" {badges_str}" if badges_str else ""
        description += f"{prefix} **{username}**{role_part} — **{bal:,}** 🪙\n"
    embed.description = description
    embed.set_footer(text="Usa /shop para comprar roles y destacarte en el ranking")
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


class BlackjackView(GuildView):
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


class CoinflipChallengeView(GuildView):
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


class DuelChallengeView(GuildView):
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


class CrashView(GuildView):
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
    await interaction.response.send_message(embed=build_shop_embed())


@tree.command(name="iteminfo", description="Muestra los detalles completos de un objeto de la tienda")
@app_commands.describe(item="ID del objeto a consultar")
async def iteminfo(interaction: discord.Interaction, item: str):
    item = normalize_shop_item_id(item)
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
                f"• Usa `/use {item}` para reclamarlo en este servidor\n"
                "• Usa `/collect` para reclamar tus ganancias\n"
                "• Cada rol tiene su propio cooldown\n"
                "• El objeto permanece en tu inventario para mantener el bonus"
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


@tree.command(name="use", description="Usa un objeto o reclama un rol de tu inventario")
@app_commands.describe(item="ID del objeto a usar o rol a reclamar")
async def use(interaction: discord.Interaction, item: str):
    item = resolve_shop_item(item) or normalize_shop_item_id(item)
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

    if item_data["category"] == "rol":
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Debes usar este comando dentro del servidor donde quieres reclamar el rol.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            role, already_has_role, error = await grant_shop_role(
                interaction.guild, interaction.user, item
            )
        except discord.Forbidden:
            error = "No tengo permiso para crear o asignar roles. Necesito **Gestionar roles**."
            role = None
            already_has_role = False
        except discord.HTTPException:
            error = "Discord no pudo crear o asignar el rol. Inténtalo de nuevo."
            role = None
            already_has_role = False
        except aiosqlite.Error:
            error = "No pude guardar el rol del servidor. El objeto sigue en tu inventario; inténtalo de nuevo."
            role = None
            already_has_role = False

        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        claim_message = (
            f"Ya tienes el rol {role.mention}."
            if already_has_role
            else f"Reclamaste {role.mention}; ya está asignado a tu cuenta."
        )
        await interaction.followup.send(
            f"{claim_message}\nEl objeto permanece en tu inventario para `/collect`.",
            ephemeral=True,
        )
        return

    if item_data["category"] == "decorativo":
        flavor = USE_FLAVOR.get(item, f"Usas **{item_data['name']}**.")
        embed = discord.Embed(title=f"✨ Usando {item_data['name']}", color=0x9B59B6)
        embed.description = flavor
        embed.set_footer(text=f"Tienes {qty} en tu inventario")
        await interaction.response.send_message(embed=embed)

    elif item == "anti_rob":
        await interaction.response.defer()
        embed = await activate_anti_rob(interaction.user, interaction.guild, qty)
        await interaction.followup.send(embed=embed)


async def use_item_autocomplete(interaction: discord.Interaction, current: str):
    t = _plain(current)
    rows = await get_inventory(str(interaction.user.id))
    choices = []
    for item_id, qty in rows:
        item = SHOP_ITEMS.get(item_id)
        if item is None:
            continue
        if t and t not in f"{_plain(item['name'])} {_plain(item_id)}":
            continue
        choices.append(app_commands.Choice(name=f"{item['name']} (x{qty})"[:100], value=item_id))
    return choices[:25]


use.autocomplete("item")(use_item_autocomplete)


class BetView(GuildView):
    def __init__(self, challenger_id: str, challenged_id: str, amount: int, challenger_name: str):
        super().__init__(timeout=60)
        self.challenger_id = challenger_id
        self.challenged_id = challenged_id
        self.amount = amount
        self.challenger_name = challenger_name
        self.message: discord.Message | None = None

    async def on_timeout(self):
        await update_balance(self.challenger_id, self.amount)
        if self.message:
            embed = discord.Embed(title="⌛ Apuesta Expirada", color=0x888888)
            embed.description = (
                f"La apuesta de **{self.amount:,}** 🪙 no fue aceptada a tiempo.\n"
                f"Se devolvió el dinero a **{self.challenger_name}**."
            )
            for item in self.children:
                item.disabled = True
            await self.message.edit(embed=embed, view=self)

    @discord.ui.button(label="✅ Aceptar", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.challenged_id:
            await interaction.response.send_message("❌ Esta apuesta no es contigo.", ephemeral=True)
            return

        challenged_balance = await get_balance(self.challenged_id)
        if challenged_balance < self.amount:
            await update_balance(self.challenger_id, self.amount)
            embed = discord.Embed(title="❌ Apuesta Cancelada", color=0xFF4444)
            embed.description = (
                f"**{interaction.user.mention}** no tiene suficientes monedas para aceptar.\n"
                f"Se devolvió el dinero al retador."
            )
            for item in self.children:
                item.disabled = True
            self.stop()
            await interaction.response.edit_message(embed=embed, view=self)
            return

        await update_balance(self.challenged_id, -self.amount)

        pot = self.amount * 2
        winner_id = random.choice([self.challenger_id, self.challenged_id])
        loser_id = self.challenged_id if winner_id == self.challenger_id else self.challenger_id

        winner_member = interaction.guild.get_member(int(winner_id))
        loser_member = interaction.guild.get_member(int(loser_id))
        winner_name = winner_member.mention if winner_member else f"<@{winner_id}>"
        loser_name = loser_member.mention if loser_member else f"<@{loser_id}>"

        await update_balance(winner_id, pot)
        winner_balance = await get_balance(winner_id)

        coin = "🪙"
        embed = discord.Embed(title="🎲 ¡Resultado de la Apuesta!", color=0xFFD700)
        embed.description = (
            f"**Bote total:** {pot:,} {coin}\n\n"
            f"🏆 **{winner_name}** ganó **{pot:,}** {coin}!\n"
            f"💸 **{loser_name}** perdió **{self.amount:,}** {coin}\n\n"
            f"Saldo del ganador: **{winner_balance:,}** {coin}"
        )
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="❌ Rechazar", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.challenged_id:
            await interaction.response.send_message("❌ Esta apuesta no es contigo.", ephemeral=True)
            return

        await update_balance(self.challenger_id, self.amount)
        embed = discord.Embed(title="🚫 Apuesta Rechazada", color=0xFF4444)
        embed.description = (
            f"**{interaction.user.mention}** rechazó la apuesta.\n"
            f"Se devolvió **{self.amount:,}** 🪙 al retador."
        )
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(embed=embed, view=self)


@tree.command(name="bet", description="Reta a otro usuario a una apuesta cara a cara")
@app_commands.describe(usuario="El usuario al que quieres retar", cantidad="Cantidad a apostar")
async def bet(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    if cantidad <= 0:
        await interaction.response.send_message("❌ La apuesta debe ser mayor a 0.", ephemeral=True)
        return
    if usuario.id == interaction.user.id:
        await interaction.response.send_message("❌ No puedes apostarte a ti mismo.", ephemeral=True)
        return
    if usuario.bot:
        await interaction.response.send_message("❌ No puedes retar a un bot.", ephemeral=True)
        return

    challenger_id = str(interaction.user.id)
    challenged_id = str(usuario.id)
    await get_or_create_user(challenger_id, interaction.user.name)
    await get_or_create_user(challenged_id, usuario.name)

    challenger_balance = await get_balance(challenger_id)
    if challenger_balance < cantidad:
        await interaction.response.send_message(
            f"❌ No tienes suficientes monedas. Tienes **{challenger_balance:,}** 🪙.", ephemeral=True
        )
        return

    await update_balance(challenger_id, -cantidad)

    embed = discord.Embed(title="🎲 ¡Desafío de Apuesta!", color=0xE67E22)
    embed.description = (
        f"**{interaction.user.mention}** reta a **{usuario.mention}** a una apuesta.\n\n"
        f"💰 **En juego:** {cantidad:,} 🪙 cada uno → **bote total: {cantidad * 2:,}** 🪙\n\n"
        f"🎯 El ganador se lleva **todo**. ¡El azar decide!\n\n"
        f"⏳ Tienes **60 segundos** para aceptar o rechazar."
    )
    embed.set_footer(text=f"Solo {usuario.display_name} puede responder")

    view = BetView(
        challenger_id=challenger_id,
        challenged_id=challenged_id,
        amount=cantidad,
        challenger_name=interaction.user.display_name
    )
    await interaction.response.send_message(embed=embed, view=view, content=usuario.mention)
    view.message = await interaction.original_response()


@tree.command(name="gift", description="Regala un objeto de tu inventario a otro usuario")
@app_commands.describe(usuario="El usuario que recibirá el regalo", item="ID del objeto a regalar")
async def gift(interaction: discord.Interaction, usuario: discord.Member, item: str):
    item = normalize_shop_item_id(item)
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

    if item in ROLE_ITEMS and await role_is_committed(sender_id, item):
        await interaction.response.send_message(
            "❌ Ese rol está prestado o publicado en el mercado de roles. Espera a que termine o retíralo.", ephemeral=True)
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
    item = normalize_shop_item_id(item)
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

    if item in ROLE_ITEMS and await role_is_committed(user_id, item):
        await interaction.response.send_message(
            "❌ Ese rol está prestado o publicado en el mercado de roles. Espera a que termine o retíralo.", ephemeral=True)
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


class TournamentView(GuildView):
    MAX_PLAYERS = 8

    def __init__(self, host_id: str, host_name: str, buy_in: int):
        super().__init__(timeout=90)
        self.host_id = host_id
        self.buy_in = buy_in
        self.host_name = host_name
        self.players: list[tuple[str, str]] = []
        self.message: discord.Message | None = None
        self.started = False

    def roster_text(self):
        if not self.players:
            return "_Nadie se ha unido todavía..._"
        lines = [f"{i+1}. {name}" for i, (_, name) in enumerate(self.players)]
        return "\n".join(lines)

    def make_embed(self):
        pot = self.buy_in * len(self.players)
        embed = discord.Embed(title="🏆 Torneo de Casino — Fase de Inscripción", color=0xE91E63)
        embed.description = (
            f"**Entry fee:** {self.buy_in:,} 🪙\n"
            f"**Bote acumulado:** {pot:,} 🪙\n"
            f"**Jugadores:** {len(self.players)}/{self.MAX_PLAYERS}\n\n"
            f"**Inscritos:**\n{self.roster_text()}\n\n"
            f"⏳ El torneo inicia en **90 segundos** o cuando haya {self.MAX_PLAYERS} jugadores.\n"
            f"El campeón se lleva **todo el bote**."
        )
        embed.set_footer(text=f"Organizado por {self.host_name}")
        return embed

    @discord.ui.button(label="🎟️ Unirse al Torneo", style=discord.ButtonStyle.primary)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.started:
            await interaction.response.send_message("❌ El torneo ya comenzó.", ephemeral=True)
            return
        uid = str(interaction.user.id)
        if any(p[0] == uid for p in self.players):
            await interaction.response.send_message("❌ Ya estás inscrito.", ephemeral=True)
            return
        bal = await get_balance(uid)
        if bal < self.buy_in:
            await interaction.response.send_message(
                f"❌ Necesitas **{self.buy_in:,}** 🪙 para entrar. Tienes **{bal:,}** 🪙.", ephemeral=True
            )
            return
        await get_or_create_user(uid, interaction.user.name)
        await update_balance(uid, -self.buy_in)
        self.players.append((uid, interaction.user.display_name))
        await interaction.response.edit_message(embed=self.make_embed(), view=self)
        if len(self.players) >= self.MAX_PLAYERS:
            self.stop()
            await self.run_tournament(interaction.channel)

    @discord.ui.button(label="🚀 Iniciar Ya", style=discord.ButtonStyle.success)
    async def start_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.host_id:
            await interaction.response.send_message("❌ Solo el organizador puede iniciar el torneo.", ephemeral=True)
            return
        if len(self.players) < 2:
            await interaction.response.send_message("❌ Necesitas al menos 2 jugadores para iniciar.", ephemeral=True)
            return
        self.stop()
        await interaction.response.defer()
        await self.run_tournament(interaction.channel)

    async def on_timeout(self):
        if self.started:
            return
        if len(self.players) < 2:
            for uid, _ in self.players:
                await update_balance(uid, self.buy_in)
            if self.message:
                embed = discord.Embed(title="⌛ Torneo Cancelado", color=0x888888)
                embed.description = "No hubo suficientes jugadores. Se devolvió el dinero."
                for item in self.children:
                    item.disabled = True
                await self.message.edit(embed=embed, view=self)
            return
        await self.run_tournament(self.message.channel if self.message else None)

    async def run_tournament(self, channel):
        if self.started:
            return
        self.started = True
        for item in self.children:
            item.disabled = True
        if self.message:
            embed = self.make_embed()
            embed.title = "🏆 ¡Torneo Iniciado!"
            embed.color = 0xFFD700
            await self.message.edit(embed=embed, view=self)

        bracket = list(self.players)
        random.shuffle(bracket)
        round_num = 1

        while len(bracket) > 1:
            next_round = []
            round_results = []

            pairs = []
            i = 0
            while i + 1 < len(bracket):
                pairs.append((bracket[i], bracket[i + 1]))
                i += 2
            if i < len(bracket):
                bye = bracket[i]
                next_round.append(bye)
                round_results.append(f"🎟️ **{bye[1]}** avanza con bye (número impar)")

            for (p1_id, p1_name), (p2_id, p2_name) in pairs:
                winner = random.choice([(p1_id, p1_name), (p2_id, p2_name)])
                loser_name = p2_name if winner[0] == p1_id else p1_name
                next_round.append(winner)
                coin = random.choice(["🦅 Cara", "🦁 Cruz"])
                round_results.append(f"**{p1_name}** vs **{p2_name}** → {coin} → 🏅 **{winner[1]}** avanza")

            embed = discord.Embed(
                title=f"⚔️ Ronda {round_num}",
                description="\n".join(round_results),
                color=0xE67E22
            )
            survivors = ", ".join(p[1] for p in next_round)
            embed.set_footer(text=f"Continúan: {survivors}")
            if channel:
                await channel.send(embed=embed)
            await asyncio.sleep(3)
            bracket = next_round
            round_num += 1

        champion_id, champion_name = bracket[0]
        pot = self.buy_in * len(self.players)
        await update_balance(champion_id, pot)
        final_balance = await get_balance(champion_id)

        embed = discord.Embed(title="🏆 ¡CAMPEÓN DEL TORNEO!", color=0xFFD700)
        embed.description = (
            f"🥇 **{champion_name}** es el campeón absoluto!\n\n"
            f"💰 Premio: **{pot:,}** 🪙\n"
            f"Saldo final: **{final_balance:,}** 🪙"
        )
        embed.set_footer(text=f"Torneo con {len(self.players)} participantes · {self.buy_in:,} 🪙 de entrada")
        if channel:
            await channel.send(embed=embed)


@tree.command(name="tournament", description="Organiza un torneo de eliminación directa con otros jugadores")
@app_commands.describe(entrada="Costo de entrada en monedas")
async def tournament(interaction: discord.Interaction, entrada: int):
    if entrada <= 0:
        await interaction.response.send_message("❌ El costo de entrada debe ser mayor a 0.", ephemeral=True)
        return

    host_id = str(interaction.user.id)
    await get_or_create_user(host_id, interaction.user.name)
    bal = await get_balance(host_id)
    if bal < entrada:
        await interaction.response.send_message(
            f"❌ Necesitas **{entrada:,}** 🪙 para crear el torneo. Tienes **{bal:,}** 🪙.", ephemeral=True
        )
        return

    await update_balance(host_id, -entrada)
    view = TournamentView(host_id=host_id, host_name=interaction.user.display_name, buy_in=entrada)
    view.players.append((host_id, interaction.user.display_name))

    await interaction.response.send_message(embed=view.make_embed(), view=view)
    view.message = await interaction.original_response()


@tree.command(name="help", description="Muestra todos los comandos del bot organizados por categoría")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎰 Casino Bot — Comandos",
        description="Todos los comandos disponibles organizados por categoría.",
        color=0xE91E63
    )

    embed.add_field(
        name="💰 Economía",
        value=(
            "`/balance` — Cartera, banco y total\n"
            "`/daily` — Recompensa diaria de 500 🪙\n"
            "`/dep <cantidad|all>` — Depositar al banco\n"
            "`/withdraw <cantidad|all>` — Retirar del banco\n"
            "`/pay @usuario cantidad` — Transferir monedas\n"
            "`/leaderboard` — Top 10 jugadores"
        ),
        inline=False
    )

    embed.add_field(
        name="🆕 Novedades",
        value=(
            "`/work` `/slut` `/crime` — Gana monedas (configurables en el panel web)\n"
            "`/top` — Ranking semanal con premios automáticos\n"
            "`/logros` — Insignias y progreso\n"
            "`/mines cantidad minas` — Buscaminas con retiro a tiempo\n"
            "`/hilo cantidad` o `,hilo cantidad` — Hi-Lo: mayor, menor o igual\n"
            "`/añadir rol` · `/quitar rol` — (admins) Roles propios en la tienda\n"
            "`/clan ...` o `,clan ...` — Clanes con banco y misiones\n"
            "`/prestar` `/devolver` `/misprestamos` — Presta roles y mira tus cobros\n"
            "`/rolmercado publicar|ver|comprar|retirar` — Vende o alquila roles\n"
            "`/ftorneo apuesta` — Torneo de luchadores con entrada y premio\n"
            "`/carcel` `/fianza` — Cárcel por robos fallidos\n"
            "`/evento` — Configura collect x2 a x50 y su duración (administradores)\n"
            "`/cancelar evento` — Termina el evento manual (administradores)"
        ),
        inline=False
    )

    embed.add_field(
        name="🎰 Juegos",
        value=(
            "`/slots cantidad` — Tragamonedas\n"
            "`/roulette cantidad color` — Ruleta rojo/negro\n"
            "`/blackjack cantidad` — Blackjack vs dealer\n"
            "`/coinflip cantidad cara|cruz` — Cara o cruz\n"
            "`/crash cantidad` — Crash: retira antes que explote"
        ),
        inline=False
    )

    embed.add_field(
        name="⚔️ PvP",
        value=(
            "`/duel @usuario cantidad` — Duelo 1v1\n"
            "`/bet @usuario cantidad` — Apuesta (acepta/rechaza)\n"
            "`/rob @usuario` — Intenta robar (40% éxito)\n"
            "`/tournament entrada` — Torneo hasta 8 jugadores"
        ),
        inline=False
    )

    embed.add_field(
        name="🛍️ Tienda e Inventario",
        value=(
            "`/shop` — Ver la tienda\n"
            "`/buy [item]` — Abrir panel de compra o comprar por ID\n"
            "`/inventory` — Ver tu inventario\n"
            "`/iteminfo item` — Info de un objeto\n"
            "`/use item` — Usar un objeto o reclamar un rol\n"
            "`/gift @usuario item` — Regalar un objeto\n"
            "`/sell item` — Vender objeto al 50%"
        ),
        inline=False
    )

    embed.add_field(
        name="⚽ Cartas de fútbol",
        value=(
            "`/comprarsobre tipo` — Comprar y abrir un sobre\n"
            "`/inventariocartas` — Ver tus cartas y duplicados\n"
            "`/coleccion [usuario]` — Ver una colección\n"
            "`/infocartas` — Ver sobres y precios"
        ),
        inline=False
    )

    embed.add_field(
        name="📋 Misiones",
        value="`/missions` — Ver misiones diarias y progreso",
        inline=False
    )

    embed.add_field(
        name="🔧 Admin",
        value=(
            "`/addmoney @usuario cantidad` — Añadir monedas\n"
            "`/removemoney @usuario cantidad` — Quitar monedas\n"
            "`/collect` — Recoger ganancias de roles"
        ),
        inline=False
    )

    embed.add_field(
        name="🛡️ Moderación (solo slash)",
        value=(
            "`/ban usuario [razón]` y `/unban user_id` — requieren **Banear miembros**\n"
            "`/kick usuario [razón]` — requiere **Expulsar miembros**\n"
            "`/mute` y `/unmute` — requieren **Administrador**\n"
            "`/clear cantidad [canal]` — requiere **Administrador**\n"
            "`/lock [canal]` y `/unlock [canal]` — requieren **Administrador**\n"
            "`/addrole usuario rol` y `/removerole usuario rol` — requieren **Administrador**"
        ),
        inline=False
    )

    embed.set_footer(text="Para ver la guía completa con ejemplos, usa `/guía`.")
    await interaction.response.send_message(embed=embed)


GUIDE_SECTIONS = (
    {
        "id": "economy",
        "title": "💰 Economía y monedas",
        "description": (
            "Las monedas del casino se muestran como 🪙. Gana con `/daily`, misiones, "
            "premios de juegos y `/collect`. Usa `/balance` para revisar cartera y banco; "
            "el dinero depositado está protegido contra robos."
        ),
        "commands": (
            "balance", "daily", "collect", "pay", "dep", "withdraw", "missions",
            "leaderboard", "ranking", "historial",
        ),
    },
    {
        "id": "games",
        "title": "🎰 Juegos y apuestas",
        "description": (
            "Las apuestas pueden darte ganancias o hacerte perder monedas. En `/roulette` "
            "puedes apostar a color, par/impar, docena o número; también admite hasta tres apuestas."
        ),
        "commands": (
            "roulette", "slots", "blackjack", "coinflip", "rob", "duel", "crash",
            "bet", "tournament", "ruleta-en-vivo",
        ),
    },
    {
        "id": "clans",
        "title": "🛡️ Clanes",
        "description": (
            "Los comandos del clan también funcionan como comandos de texto con coma. "
            "Escribe `,clan ayuda` para ver esta lista en el chat."
        ),
        "commands": ("clan",),
    },
    {
        "id": "events",
        "title": "🎉 Eventos de collect",
        "description": (
            "Los administradores pueden iniciar eventos de collect x2 a x50 y elegir su duración "
            "desde el panel de `/evento`. Los demás usuarios pueden consultar el estado."
        ),
        "commands": ("evento", "cancelar"),
    },
    {
        "id": "shop",
        "title": "🛍️ Tienda, objetos y roles",
        "description": (
            "Abre `/shop` y compra con `/buy <item>`. Por ejemplo, compra `bronce` y luego "
            "usa `/use bronce` para crear y reclamar el rol en el servidor. El objeto queda "
            "en tu inventario para que `/collect` siga pagando sus ganancias."
        ),
        "commands": (
            "shop", "store", "buy", "inventory", "iteminfo", "use", "gift", "sell",
        ),
    },
    {
        "id": "fighters",
        "title": "🥊 Luchadores y puntos de mejora",
        "description": (
            "Consulta y compra luchadores con `/fighters` y `/buyfighter`, y pelea con `/fight`. "
            "En un combate el ganador gana 15 XP y el otro luchador 5 XP; cada nivel otorga "
            "5 puntos de mejora. `/addpuntos ataque 2` gasta puntos: cada punto suma +2 ataque, "
            "+2 defensa o +5 salud. Elige `ataque`, `defensa` o `salud`."
        ),
        "commands": (
            "fighters", "buyfighter", "myfighter", "fight", "addpuntos", "ftorneo",
        ),
    },
    {
        "id": "football",
        "title": "⚽ Cartas de fútbol",
        "description": (
            "Revisa `/infocartas`, compra sobres con `/comprarsobre`, consulta tu colección "
            "y publica cartas en el mercado. Los comandos muestran el ID o número de publicación "
            "que necesitas para vender, comprar o retirar una oferta."
        ),
        "commands": (
            "abrirpaquete", "comprarsobre", "coleccion", "inventariocartas",
            "infocartas", "vender", "mercado", "comprar", "cancelarventa",
            "misventas", "intercambiar",
        ),
    },
    {
        "id": "admin",
        "title": "🛡️ Administración y moderación",
        "description": (
            "Permisos: `/ban` y `/unban` requieren **Banear miembros**; `/kick` requiere "
            "**Expulsar miembros**. Los demás comandos de moderación requieren **Administrador**. "
            "`/addmoney`, `/removemoney` y `/addlevel` también son para administradores. "
            "`/resetmoney` reinicia tu cartera; solo un administrador puede elegir a otra persona. "
            "El bot también necesita sus permisos de Discord y una jerarquía de roles correcta."
        ),
        "commands": (
            "ban", "unban", "kick", "mute", "unmute", "clear", "lock", "unlock",
            "addrole", "removerole", "addmoney", "removemoney", "resetmoney", "addlevel",
        ),
    },
    {
        "id": "general",
        "title": "📚 Ayuda general",
        "description": (
            "Los campos muestran cada comando slash registrado, su uso y sus opciones. "
            "Los valores entre `< >` son obligatorios; los que están entre `[ ]` son opcionales. "
            "Discord te permite seleccionar usuarios, canales y roles desde el menú del comando."
        ),
        "commands": ("help", "guía"),
    },
)


def build_guide_command_value(command: app_commands.Command) -> str:
    arguments = []
    details = []
    parameters = getattr(command, "parameters", [])
    for parameter in parameters:
        token = f"<{parameter.name}>" if parameter.required else f"[{parameter.name}]"
        arguments.append(token)

        requirement = "obligatorio" if parameter.required else "opcional"
        hint = parameter.description or parameter.name.replace("_", " ")
        if parameter.choices and len(parameters) <= 2:
            choices = ", ".join(choice.name for choice in parameter.choices[:6])
            hint = f"{hint}. Opciones: {choices}"
        details.append(f"• `{parameter.name}` ({requirement}): {hint}")

    usage = f"/{command.name}"
    if arguments:
        usage += " " + " ".join(arguments)
    value = f"Uso: `{usage}`\n{command.description or 'Comando del bot.'}"
    if details:
        value += "\n" + "\n".join(details)
    if len(value) > 1000:
        value = value[:997] + "…"
    return value


def build_guide_pages() -> list[dict]:
    registered = {command.name: command for command in tree.get_commands()}
    pages = []
    covered: set[str] = set()

    for section in GUIDE_SECTIONS:
        commands = [
            registered[name]
            for name in section["commands"]
            if name in registered
        ]
        covered.update(command.name for command in commands)
        page = {
            "title": section["title"],
            "description": section["description"],
            "commands": commands,
            "extra_fields": [],
        }

        if section["id"] == "economy":
            page["extra_fields"].append(
                (
                    "Comandos de texto para ganar monedas",
                    (
                        "`,work` — gana entre 1.000 y 100.000 🪙.\n"
                        "`,slut` y `,crime` — 60% de éxito y 40% de riesgo de perder monedas.\n"
                        "`,lottery [cantidad]` — compra boletos; `,lottery info` muestra el bote. "
                        "Estos comandos se escriben con coma en el chat, no como slash."
                    ),
                )
            )

        if section["id"] == "shop":
            role_lines = [
                (
                    f"**{item['name'].split('Rol:', 1)[-1].strip()}** — "
                    f"+{item['collect_bonus']:,} 🪙 cada {item['collect_hours']} h"
                )
                for item in SHOP_ITEMS.values()
                if item.get("category") == "rol"
            ]
            if role_lines:
                page["extra_fields"].append(("Ganancias de roles", "\n".join(role_lines)))

        if section["id"] == "clans":
            page["extra_fields"].append(
                (
                    "Comandos con coma",
                    (
                        "`,clan crear <nombre>` · `,clan unirse <nombre>`\n"
                        "`,clan salir` · `,clan info [nombre]`\n"
                        "`,clan depositar <cantidad>` · `,clan retirar <cantidad> [@miembro]`\n"
                        "`,clan invitar @usuario` · `,clan expulsar @usuario`\n"
                        "`,clan acceso abierto|cerrado` · `,clan misiones` · `,clan top`\n"
                        "`,clan disolver confirmar` · Los nombres de clan pueden tener espacios."
                    ),
                )
            )

        if section["id"] == "events":
            page["extra_fields"].append(
                (
                    "Cómo usar los eventos",
                    (
                        "`/evento` — Los administradores eligen multiplicador x2–x50 y duración en días.\n"
                        "`/cancelar evento` — Termina el evento manual; requiere Administrador.\n"
                        "El evento automático de fin de semana no se cancela con este comando."
                    ),
                )
            )

        if commands or page["extra_fields"]:
            pages.append(page)

    uncategorized = [
        command for name, command in registered.items() if name not in covered
    ]
    if uncategorized:
        pages.append(
            {
                "title": "📎 Otros comandos",
                "description": "Otros comandos slash registrados en el bot.",
                "commands": uncategorized,
                "extra_fields": [],
            }
        )
    return pages


class GuideView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.pages = build_guide_pages()
        self.page_index = 0
        self.update_navigation()

    def update_navigation(self):
        self.previous_button.disabled = self.page_index == 0
        self.next_button.disabled = self.page_index >= len(self.pages) - 1

    def make_embed(self) -> discord.Embed:
        page = self.pages[self.page_index]
        embed = discord.Embed(
            title=f"Guía del bot · {page['title']}",
            description=page["description"],
            color=0xE91E63,
        )
        for command in page["commands"]:
            embed.add_field(
                name=f"/{command.name}",
                value=build_guide_command_value(command),
                inline=False,
            )
        for name, value in page["extra_fields"]:
            embed.add_field(name=name, value=value, inline=False)
        embed.set_footer(
            text=(
                f"Página {self.page_index + 1}/{len(self.pages)} · "
                "Los botones solo funcionan para quien abrió la guía."
            )
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Solo la persona que abrió esta guía puede cambiar de página.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Anterior", emoji="◀", style=discord.ButtonStyle.secondary)
    async def previous_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page_index = max(0, self.page_index - 1)
        self.update_navigation()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="Siguiente", emoji="▶", style=discord.ButtonStyle.secondary)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page_index = min(len(self.pages) - 1, self.page_index + 1)
        self.update_navigation()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)


@tree.command(name="guía", description="Guía completa de comandos, monedas, juegos y roles")
async def guia(interaction: discord.Interaction):
    view = GuideView(interaction.user.id)
    await interaction.response.send_message(
        embed=view.make_embed(),
        view=view,
        ephemeral=True,
    )


async def get_fighter_stats(user_id: str, fighter_id: str) -> dict:
    base = FIGHTERS[fighter_id]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT level, xp, points, bonus_hp, bonus_attack, bonus_defense FROM fighter_levels WHERE user_id=? AND fighter_id=?",
            (user_id, fighter_id)
        ) as cur:
            row = await cur.fetchone()
    level, xp, pts, b_hp, b_atk, b_def = row if row else (1, 0, 0, 0, 0, 0)
    return {
        "name": base["name"],
        "hp": base["hp"] + b_hp,
        "attack": base["attack"] + b_atk,
        "defense": base["defense"] + b_def,
        "level": level, "xp": xp, "points": pts,
        "bonus_hp": b_hp, "bonus_attack": b_atk, "bonus_defense": b_def,
        "base_id": fighter_id,
    }


async def add_fighter_xp(user_id: str, fighter_id: str, xp_gain: int) -> tuple[int, int, int]:
    """Returns (new_level, new_xp, points_gained)"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT level, xp, points FROM fighter_levels WHERE user_id=? AND fighter_id=?",
            (user_id, fighter_id)
        ) as cur:
            row = await cur.fetchone()
    level, xp, points = row if row else (1, 0, 0)
    xp += xp_gain
    points_gained = 0
    while xp >= level * 20:
        xp -= level * 20
        level += 1
        points += 5
        points_gained += 5
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO fighter_levels (user_id, fighter_id, level, xp, points) VALUES (?,?,?,?,?) "
            "ON CONFLICT(user_id, fighter_id) DO UPDATE SET level=excluded.level, xp=excluded.xp, points=excluded.points",
            (user_id, fighter_id, level, xp, points)
        )
        await db.commit()
    return level, xp, points_gained


def simulate_fight_stats(s1: dict, s2: dict) -> tuple[int, str]:
    """0 = primer luchador gana, 1 = segundo luchador gana"""
    hp1, hp2 = s1["hp"], s2["hp"]
    log_lines = []
    turn = 0
    while hp1 > 0 and hp2 > 0:
        if turn % 2 == 0:
            dmg = max(1, s1["attack"] - s2["defense"] // 2 + random.randint(-4, 6))
            hp2 -= dmg
            log_lines.append(f"⚔️ **{s1['name']}** golpea por **{dmg}** dmg → {s2['name']} HP: {max(0, hp2)}")
        else:
            dmg = max(1, s2["attack"] - s1["defense"] // 2 + random.randint(-4, 6))
            hp1 -= dmg
            log_lines.append(f"⚔️ **{s2['name']}** golpea por **{dmg}** dmg → {s1['name']} HP: {max(0, hp1)}")
        turn += 1
        if turn > 40:
            break
    winner_idx = 0 if hp1 > hp2 else 1
    return winner_idx, "\n".join(log_lines[-6:])


def simulate_fight(f1_id: str, f2_id: str) -> tuple[str, str]:
    s1 = {**FIGHTERS[f1_id]}; s2 = {**FIGHTERS[f2_id]}
    idx, log = simulate_fight_stats(s1, s2)
    return (f1_id if idx == 0 else f2_id), log


async def get_current_fighter_id(user_id: str) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT fighter_id FROM fighters WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else None


FIGHTER_PURCHASE_LOCKS: dict[str, asyncio.Lock] = {}


async def complete_fighter_purchase(
    user: discord.User | discord.Member,
    fighter_id: str,
    *,
    expected_current_id: str | None = None,
) -> tuple[discord.Embed | None, str | None]:
    user_id = str(user.id)
    lock = FIGHTER_PURCHASE_LOCKS.setdefault(user_id, asyncio.Lock())
    async with lock:
        await get_or_create_user(user_id, user.name)
        current_id = await get_current_fighter_id(user_id)
        if current_id == fighter_id:
            return None, "Ya tienes activo ese luchador. No se descontaron monedas."
        if current_id and current_id != expected_current_id:
            current_name = FIGHTERS.get(current_id, {}).get("name", current_id)
            return None, (
                f"Ya tienes activo a **{current_name}**. Debes confirmar antes de reemplazarlo."
            )
        if expected_current_id is not None and current_id != expected_current_id:
            return None, (
                "Tu luchador activo cambió desde que abriste la confirmación. "
                "Vuelve a abrir la tienda."
            )

        fighter = FIGHTERS[fighter_id]
        balance = await get_balance(user_id)
        if balance < fighter["price"]:
            return None, (
                f"Te faltan **{fighter['price'] - balance:,}** 🪙 para comprar "
                f"**{fighter['name']}**."
            )

        await update_balance(user_id, -fighter["price"])
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO fighters (user_id, fighter_id) VALUES (?, ?)",
                (user_id, fighter_id),
            )
            await db.commit()

    embed = discord.Embed(title="🥊 ¡Luchador comprado!", color=0x00FF88)
    embed.description = (
        f"Ahora tienes a **{fighter['name']}** en tu equipo.\n\n"
        f"❤️ HP: {fighter['hp']} | ⚔️ ATK: {fighter['attack']} | "
        f"🛡️ DEF: {fighter['defense']}\n\n"
        "Usa `/fight @usuario` para retar a alguien."
    )
    return embed, None


def build_fighter_shop_embed() -> discord.Embed:
    embed = discord.Embed(title="🥊 Luchadores del Casino", color=0xFF6B00)
    embed.description = (
        "Elige un luchador en el menú para comprarlo.\n"
        "Si ya tienes uno, el bot te pedirá confirmar antes de reemplazarlo.\n\u200b"
    )
    for fid, f in FIGHTERS.items():
        embed.add_field(
            name=f"{f['name']} — `{fid}`",
            value=f"💰 {f['price']:,} 🪙\n❤️ HP: {f['hp']} | ⚔️ ATK: {f['attack']} | 🛡️ DEF: {f['defense']}\n_{f['description']}_",
            inline=False
        )
    return embed


class FighterReplaceConfirmView(GuildView):
    def __init__(self, owner_id: int, fighter_id: str, expected_current_id: str):
        super().__init__(timeout=120)
        self.owner_id = owner_id
        self.fighter_id = fighter_id
        self.expected_current_id = expected_current_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Esta confirmación pertenece a otra persona.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Confirmar compra", style=discord.ButtonStyle.danger)
    async def confirm_purchase(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="Procesando la compra…", embed=None, view=None
        )
        embed, error = await complete_fighter_purchase(
            interaction.user,
            self.fighter_id,
            expected_current_id=self.expected_current_id,
        )
        if error:
            await interaction.followup.send(error, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)
        self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel_purchase(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="Compra cancelada. No se descontaron monedas.",
            embed=None,
            view=None,
        )
        self.stop()


async def offer_fighter_purchase(
    interaction: discord.Interaction, fighter_id: str, *, edit_message: bool = False
):
    current_id = await get_current_fighter_id(str(interaction.user.id))
    if current_id == fighter_id:
        message = "Ya tienes activo ese luchador. No se descontaron monedas."
        if edit_message:
            await interaction.response.edit_message(
                content=message, embed=None, view=None
            )
        else:
            await interaction.response.send_message(message, ephemeral=True)
        return

    if current_id:
        current_name = FIGHTERS.get(current_id, {}).get("name", current_id)
        new_fighter = FIGHTERS[fighter_id]
        confirm_embed = discord.Embed(
            title="⚠️ Reemplazar luchador activo",
            description=(
                f"Comprar **{new_fighter['name']}** cuesta **{new_fighter['price']:,}** 🪙 "
                f"y reemplazará a **{current_name}** como tu luchador activo. "
                "¿Quieres continuar?"
            ),
            color=0xE67E22,
        )
        confirm_view = FighterReplaceConfirmView(
            interaction.user.id, fighter_id, current_id
        )
        if edit_message:
            await interaction.response.edit_message(
                content=None, embed=confirm_embed, view=confirm_view
            )
        else:
            await interaction.response.send_message(
                embed=confirm_embed, view=confirm_view, ephemeral=True
            )
        return

    if edit_message:
        await interaction.response.edit_message(
            content="Procesando compra…", embed=None, view=None
        )
    else:
        await interaction.response.defer(ephemeral=True)
    embed, error = await complete_fighter_purchase(interaction.user, fighter_id)
    if error:
        await interaction.followup.send(error, ephemeral=True)
    else:
        await interaction.followup.send(embed=embed, ephemeral=True)


class FighterBuySelect(discord.ui.Select):
    def __init__(self, owner_id: int):
        self.owner_id = owner_id
        options = [
            discord.SelectOption(
                label=f"{fighter['name']} · {fighter_id}"[:100],
                value=fighter_id,
                description=(
                    f"{fighter['price']:,} monedas · HP {fighter['hp']} · "
                    f"ATK {fighter['attack']} · DEF {fighter['defense']}"
                )[:100],
            )
            for fighter_id, fighter in FIGHTERS.items()
        ]
        super().__init__(
            placeholder="Elige un luchador para comprar",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Este panel pertenece a otra persona.", ephemeral=True
            )
            return
        view = self.view
        if view is None or view.purchase_completed:
            await interaction.response.send_message(
                "Este panel ya fue utilizado. Ejecuta `/fighters` para abrir otro.",
                ephemeral=True,
            )
            return
        view.purchase_completed = True
        await offer_fighter_purchase(
            interaction, self.values[0], edit_message=True
        )


class FighterShopView(GuildView):
    def __init__(self, owner_id: int):
        super().__init__(timeout=180)
        self.purchase_completed = False
        self.add_item(FighterBuySelect(owner_id))


@tree.command(name="fighters", description="Abre la tienda interactiva de luchadores")
async def fighters_slash(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=build_fighter_shop_embed(),
        view=FighterShopView(interaction.user.id),
        ephemeral=True,
    )


def resolve_fighter(text: str) -> str | None:
    t = str(text).lower().strip()
    if t in FIGHTERS:
        return t
    p = _plain(text)
    if not p:
        return None
    for k, f in FIGHTERS.items():
        if p in (_plain(k), _plain(f["name"])):
            return k
    found = [k for k, f in FIGHTERS.items() if p in _plain(f["name"])]
    return found[0] if len(found) == 1 else None


async def fighter_autocomplete(interaction: discord.Interaction, current: str):
    p = _plain(current)
    out = []
    for k, f in FIGHTERS.items():
        if p and p not in f"{_plain(f['name'])} {_plain(k)}":
            continue
        name = f"{f['name']} — {f['price']:,} 🪙 · HP {f['hp']} ATK {f['attack']} DEF {f['defense']}"
        out.append(app_commands.Choice(name=name[:100], value=k))
    return out[:25]


@tree.command(name="buyfighter", description="Compra un luchador: elige de la lista o abre el panel")
@app_commands.describe(luchador="Elige el luchador de la lista; vacío = abrir el panel")
async def buyfighter_slash(
    interaction: discord.Interaction, luchador: str | None = None
):
    fighter_id = resolve_fighter(luchador) if luchador else None
    if fighter_id is None:
        note = f"❌ No encontré **{luchador}**. Elige uno en el panel:" if luchador else None
        await interaction.response.send_message(
            note,
            embed=build_fighter_shop_embed(),
            view=FighterShopView(interaction.user.id),
            ephemeral=True,
        )
        return
    await offer_fighter_purchase(interaction, fighter_id)


buyfighter_slash.autocomplete("luchador")(fighter_autocomplete)


@tree.command(name="myfighter", description="Muestra tu luchador actual")
async def myfighter_slash(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    await interaction.response.defer()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT fighter_id FROM fighters WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
    if not row:
        await interaction.followup.send("❌ No tienes luchador. Compra uno con `/buyfighter`.", ephemeral=True)
        return
    fid = row[0]
    s = await get_fighter_stats(user_id, fid)
    base = FIGHTERS[fid]
    xp_needed = s["level"] * 20
    bar_filled = int((s["xp"] / xp_needed) * 10)
    xp_bar = "█" * bar_filled + "░" * (10 - bar_filled)
    embed = discord.Embed(title=f"🥊 {s['name']} — Nivel {s['level']}", color=0xFF6B00)
    embed.description = (
        f"**Stats actuales:**\n"
        f"❤️ HP: **{s['hp']}** (+{s['bonus_hp']})\n"
        f"⚔️ ATK: **{s['attack']}** (+{s['bonus_attack']})\n"
        f"🛡️ DEF: **{s['defense']}** (+{s['bonus_defense']})\n\n"
        f"📊 XP: `{xp_bar}` {s['xp']}/{xp_needed}\n"
        f"🎯 Puntos disponibles: **{s['points']}**\n\n"
        f"_{base['description']}_\n\n"
        f"Usa `,addpuntos <stat> <cantidad>` para mejorar tu luchador.\n"
        f"Stats: `ataque`, `defensa`, `salud`"
    )
    await interaction.followup.send(embed=embed)


@tree.command(name="fight", description="Reta a otro usuario a una pelea entre luchadores")
@app_commands.describe(usuario="Usuario al que quieres retar")
async def fight_slash(interaction: discord.Interaction, usuario: discord.Member):
    uid1 = str(interaction.user.id)
    uid2 = str(usuario.id)
    if uid1 == uid2:
        await interaction.response.send_message("❌ No puedes pelearte contigo mismo.", ephemeral=True)
        return
    if usuario.bot:
        await interaction.response.send_message("❌ No puedes retar a un bot.", ephemeral=True)
        return
    await interaction.response.defer()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT last_fight FROM fight_cooldowns WHERE user_id = ?", (uid1,)) as cur:
            crow = await cur.fetchone()
    if crow and crow[0]:
        diff = datetime.utcnow() - datetime.fromisoformat(crow[0])
        if diff < timedelta(seconds=30):
            rem = timedelta(seconds=30) - diff
            s = int(rem.total_seconds())
            await interaction.followup.send(f"⏰ Espera **{s}s** antes de volver a pelear.", ephemeral=True)
            return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT fighter_id FROM fighters WHERE user_id = ?", (uid1,)) as cur:
            r1 = await cur.fetchone()
        async with db.execute("SELECT fighter_id FROM fighters WHERE user_id = ?", (uid2,)) as cur:
            r2 = await cur.fetchone()
    if not r1:
        await interaction.followup.send("❌ No tienes luchador. Compra uno con `/buyfighter`.", ephemeral=True)
        return
    if not r2:
        await interaction.followup.send(f"❌ **{usuario.name}** no tiene luchador.", ephemeral=True)
        return
    (s1, s2), loser_bal_placeholder = await asyncio.gather(
        asyncio.gather(get_fighter_stats(uid1, r1[0]), get_fighter_stats(uid2, r2[0])),
        asyncio.sleep(0)
    )
    win_idx, battle_log = simulate_fight_stats(s1, s2)
    winner_id = uid1 if win_idx == 0 else uid2
    loser_id  = uid2 if win_idx == 0 else uid1
    winner_fid = r1[0] if win_idx == 0 else r2[0]
    loser_fid  = r2[0] if win_idx == 0 else r1[0]
    winner_user = interaction.user if winner_id == uid1 else usuario
    loser_user  = usuario if winner_id == uid1 else interaction.user
    loser_bal = await get_balance(loser_id)
    prize = max(1, int(loser_bal * 0.10))
    now_str = datetime.utcnow().isoformat()
    await asyncio.gather(
        update_balance(loser_id, -prize),
        update_balance(winner_id, prize),
    )
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO fight_cooldowns (user_id, last_fight) VALUES (?, ?)",
                         (uid1, now_str))
        await db.commit()
    (new_lvl, _, pts_gained), _ = await asyncio.gather(
        add_fighter_xp(winner_id, winner_fid, 15),
        add_fighter_xp(loser_id, loser_fid, 5),
    )
    level_up_msg = f"\n🆙 **¡{winner_user.display_name} subió al nivel {new_lvl}!** +{pts_gained} puntos" if pts_gained else ""
    embed = discord.Embed(title="🥊 ¡COMBATE!", color=0xFF0000)
    embed.description = (
        f"**{interaction.user.display_name}** ({s1['name']} Nv.{s1['level']}) vs "
        f"**{usuario.display_name}** ({s2['name']} Nv.{s2['level']})\n\n"
        f"{battle_log}\n\n"
        f"🏆 **¡{winner_user.mention} gana!**\n"
        f"💰 Premio: **{prize:,}** 🪙 de {loser_user.mention}"
        f"{level_up_msg}"
    )
    await interaction.followup.send(embed=embed)


FIGHTER_TOURNAMENT_PRIZE = 60_000_000
FIGHTER_TOURNAMENT_RAKE_PERCENT = 5   # comisión del casino cuando el torneo tiene apuesta de entrada

class FighterTournamentView(GuildView):
    MAX_PLAYERS = 8

    def __init__(self, host_id: str, host_name: str, entry_fee: int = 0):
        super().__init__(timeout=90)
        self.host_id = host_id
        self.host_name = host_name
        self.entry_fee = entry_fee
        self.players: list[tuple[str, str, str]] = []  # (user_id, display_name, fighter_id)
        self.message: discord.Message | None = None
        self.started = False

    def prize_for(self, player_count: int) -> int:
        """Sin apuesta: premio fijo. Con apuesta: el pozo de entradas menos la comisión."""
        if self.entry_fee <= 0:
            return FIGHTER_TOURNAMENT_PRIZE
        return self.entry_fee * player_count * (100 - FIGHTER_TOURNAMENT_RAKE_PERCENT) // 100

    def prize_text(self) -> str:
        if self.entry_fee <= 0:
            return f"El campeón gana **{FIGHTER_TOURNAMENT_PRIZE:,}** 🪙"
        return (f"Entrada: **{self.entry_fee:,}** 🪙 por jugador · el campeón se lleva el pozo "
                f"(**{self.prize_for(len(self.players)):,}** 🪙 ahora, comisión {FIGHTER_TOURNAMENT_RAKE_PERCENT}%)")

    def roster_text(self):
        if not self.players:
            return "_Nadie se ha unido todavía..._"
        lines = []
        for i, (_, name, fid) in enumerate(self.players):
            f = FIGHTERS[fid]
            lines.append(f"{i+1}. **{name}** — {f['name']}")
        return "\n".join(lines)

    def make_embed(self):
        embed = discord.Embed(title="🥊 Torneo de Luchadores — Inscripción Abierta", color=0xFF6B00)
        embed.description = (
            f"🏆 {self.prize_text()}\n"
            f"👥 Jugadores: {len(self.players)}/{self.MAX_PLAYERS}\n\n"
            f"**Participantes:**\n{self.roster_text()}\n\n"
            f"⏳ El torneo inicia en **90 segundos** o cuando haya {self.MAX_PLAYERS} jugadores.\n"
            f"_Necesitas tener un luchador (`,buyfighter`) para inscribirte._"
        )
        embed.set_footer(text=f"Organizado por {self.host_name}")
        return embed

    @discord.ui.button(label="⚔️ Unirme al Torneo", style=discord.ButtonStyle.danger)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if self.started:
            await interaction.response.send_message("❌ El torneo ya empezó.", ephemeral=True)
            return
        if any(p[0] == uid for p in self.players):
            await interaction.response.send_message("❌ Ya estás inscrito.", ephemeral=True)
            return
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT fighter_id FROM fighters WHERE user_id = ?", (uid,)) as cur:
                row = await cur.fetchone()
        if not row:
            await interaction.response.send_message("❌ No tienes luchador. Compra uno con `,buyfighter`.", ephemeral=True)
            return
        if self.entry_fee > 0:
            balance = await get_balance(uid)
            if balance < self.entry_fee:
                await interaction.response.send_message(
                    f"❌ La entrada cuesta **{self.entry_fee:,}** 🪙 y tienes **{balance:,}** 🪙.", ephemeral=True)
                return
            await update_balance(uid, -self.entry_fee)
        self.players.append((uid, interaction.user.display_name, row[0]))
        await interaction.response.edit_message(embed=self.make_embed(), view=self)
        if len(self.players) >= self.MAX_PLAYERS:
            await self.run_tournament(interaction.message)

    async def on_timeout(self):
        if not self.started and self.message:
            await self.run_tournament(self.message)

    async def run_tournament(self, msg: discord.Message):
        if self.started:
            return
        self.started = True
        self.stop()

        channel = msg.channel
        players = list(self.players)

        if len(players) < 2:
            embed = discord.Embed(title="❌ Torneo Cancelado", color=0xFF4444)
            embed.description = "No hubo suficientes participantes (mínimo 2)."
            if self.entry_fee > 0 and players:
                for p in players:
                    await update_balance(p[0], self.entry_fee)
                embed.description += "\n💸 Se devolvieron las entradas."
            await channel.send(embed=embed)
            return
        prize = self.prize_for(len(players))

        embed = discord.Embed(title="🥊 ¡TORNEO DE LUCHADORES INICIADO!", color=0xFF6B00)
        names = "\n".join(f"• **{n}** ({FIGHTERS[fid]['name']})" for _, n, fid in players)
        embed.description = f"**{len(players)} luchadores** entran al ring:\n\n{names}\n\n_¡Que comience la batalla!_"
        await channel.send(embed=embed)
        await asyncio.sleep(2)

        round_num = 1
        while len(players) > 1:
            embed = discord.Embed(title=f"🔔 Ronda {round_num}", color=0xFFAA00)
            round_text = []
            next_round = []
            random.shuffle(players)

            i = 0
            while i < len(players):
                if i + 1 < len(players):
                    p1 = players[i]; p2 = players[i + 1]
                    s1 = await get_fighter_stats(p1[0], p1[2])
                    s2 = await get_fighter_stats(p2[0], p2[2])
                    win_idx, log = simulate_fight_stats(s1, s2)
                    winner = p1 if win_idx == 0 else p2
                    loser  = p2 if win_idx == 0 else p1
                    w_fid = winner[2]; l_fid = loser[2]
                    new_lvl, _, pts_g = await add_fighter_xp(winner[0], w_fid, 20)
                    await add_fighter_xp(loser[0], l_fid, 5)
                    lvl_note = f" 🆙Nv.{new_lvl}" if pts_g else ""
                    round_text.append(
                        f"⚔️ **{p1[1]}** ({s1['name']} Nv.{s1['level']}) vs **{p2[1]}** ({s2['name']} Nv.{s2['level']})\n"
                        f"{log}\n"
                        f"✅ Avanza: **{winner[1]}**{lvl_note}\n"
                    )
                    next_round.append(winner)
                    i += 2
                else:
                    round_text.append(f"🎯 **{players[i][1]}** pasa directo (sin rival)")
                    next_round.append(players[i])
                    i += 1

            embed.description = "\n\n".join(round_text)
            await channel.send(embed=embed)
            await asyncio.sleep(2)
            players = next_round
            round_num += 1

        champion = players[0]
        await update_balance(champion[0], prize)
        champ_bal = await get_balance(champion[0])

        embed = discord.Embed(title="🏆 ¡CAMPEÓN DEL TORNEO!", color=0xFFD700)
        embed.description = (
            f"👑 **<@{champion[0]}> es el campeón!**\n"
            f"Luchador: **{FIGHTERS[champion[2]]['name']}**\n\n"
            f"💰 Premio: **{prize:,}** 🪙\n"
            f"💼 Saldo nuevo: **{champ_bal:,}** 🪙"
        )
        await channel.send(embed=embed)


from typing import Optional as _Optional

STAT_INFO = {
    "ataque":  ("⚔️", "Ataque",  "bonus_attack",  2),
    "defensa": ("🛡️", "Defensa", "bonus_defense", 2),
    "salud":   ("❤️", "Salud",   "bonus_hp",      5),
}
_STAT_ALIASES = {
    "atk": "ataque", "attack": "ataque", "ataque": "ataque",
    "def": "defensa", "defense": "defensa", "defensa": "defensa",
    "hp": "salud", "vida": "salud", "salud": "salud",
}


def resolve_stat(text: str) -> str | None:
    p = _plain(text)
    if p in _STAT_ALIASES:
        return _STAT_ALIASES[p]
    found = [v for k, v in _STAT_ALIASES.items() if p and k.startswith(p)]
    return found[0] if found and len(set(found)) == 1 else None


async def stat_autocomplete(interaction: discord.Interaction, current: str):
    p = _plain(current)
    out = []
    for key, (emoji, label, _col, per) in STAT_INFO.items():
        if p and p not in f"{_plain(label)} {key}":
            continue
        out.append(app_commands.Choice(name=f"{emoji} {label} (+{per} por punto)", value=key))
    return out


async def _current_fighter_id(user_id: str) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT fighter_id FROM fighters WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
    return row[0] if row and row[0] in FIGHTERS else None


async def points_panel_embed(user_id: str):
    """Devuelve (embed, error, stats)."""
    fid = await _current_fighter_id(user_id)
    if fid is None:
        return None, "❌ No tienes luchador. Compra uno con `/buyfighter`.", None
    s = await get_fighter_stats(user_id, fid)
    embed = discord.Embed(title="📈 Mejorar luchador", color=0x9B59B6)
    text = (
        f"**{s['name']}** · Nivel **{s['level']}**\n"
        f"🎯 Puntos disponibles: **{s['points']}**\n\n"
        f"❤️ HP **{s['hp']}** · ⚔️ ATK **{s['attack']}** · 🛡️ DEF **{s['defense']}**\n\n"
    )
    if s["points"] > 0:
        text += "Elige qué estadística quieres mejorar:"
    else:
        text += "No tienes puntos por ahora. Ganas **5** puntos cada vez que tu luchador sube de nivel."
    embed.description = text
    embed.set_footer(text="⚔️ Ataque +2 por punto · 🛡️ Defensa +2 por punto · ❤️ Salud +5 por punto")
    return embed, None, s


def stat_quantity_embed(stat: str, points: int) -> discord.Embed:
    emoji, label, _col, per = STAT_INFO[stat]
    embed = discord.Embed(title=f"{emoji} Mejorar {label}", color=0x9B59B6)
    embed.description = (
        f"🎯 Puntos disponibles: **{points}**\n"
        f"Cada punto suma **+{per}** de {label.lower()}.\n\n"
        "¿Cuántos puntos quieres invertir?"
    )
    return embed


async def apply_stat_points(user_id: str, stat: str, cantidad: int):
    """Devuelve (embed, error, puntos_restantes)."""
    emoji, label, col, per = STAT_INFO[stat]
    if cantidad > ADDPUNTOS_MAX:
        return None, f"❌ El máximo por uso es **{ADDPUNTOS_MAX:,}** puntos.", 0
    fid = await _current_fighter_id(user_id)
    if fid is None:
        return None, "❌ No tienes luchador. Compra uno con `/buyfighter`.", 0
    gain = cantidad * per
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            f"UPDATE fighter_levels SET points = points - ?, {col} = {col} + ? "
            "WHERE user_id = ? AND fighter_id = ? AND points >= ?",
            (cantidad, gain, user_id, fid, cantidad),
        )
        changed = cur.rowcount
        await db.commit()
    s = await get_fighter_stats(user_id, fid)
    if not changed:
        return None, f"❌ Solo tienes **{s['points']}** puntos disponibles.", s["points"]
    embed = discord.Embed(title="📈 ¡Stat Mejorado!", color=0x00FF88)
    embed.description = (
        f"{emoji} **{label}** +{gain} puntos de stat\n"
        f"🎯 Puntos restantes: **{s['points']}**\n\n"
        f"**Stats actuales de {s['name']}:**\n"
        f"❤️ HP: **{s['hp']}** | ⚔️ ATK: **{s['attack']}** | 🛡️ DEF: **{s['defense']}**"
    )
    if s["points"] > 0:
        embed.set_footer(text="Elige otra estadística abajo para seguir mejorando.")
    return embed, None, s["points"]


async def _apply_and_show(interaction: discord.Interaction, owner_id: str, stat: str, amount: int):
    embed, error, remaining = await apply_stat_points(owner_id, stat, amount)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    await interaction.response.edit_message(
        embed=embed, view=StatPanelView(owner_id) if remaining > 0 else None
    )


class StatSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=label, value=key, emoji=emoji, description=f"+{per} por punto invertido"
            )
            for key, (emoji, label, _col, per) in STAT_INFO.items()
        ]
        super().__init__(
            placeholder="Elige la estadística a mejorar", min_values=1, max_values=1, options=options
        )

    async def callback(self, interaction: discord.Interaction):
        owner_id = self.view.owner_id
        stat = self.values[0]
        _embed, error, s = await points_panel_embed(owner_id)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        if s["points"] <= 0:
            await interaction.response.send_message("❌ No tienes puntos disponibles.", ephemeral=True)
            return
        await interaction.response.edit_message(
            embed=stat_quantity_embed(stat, s["points"]),
            view=StatQuantityView(owner_id, stat, s["points"]),
        )


class StatPanelView(GuildView):
    def __init__(self, owner_id: str):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.add_item(StatSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.owner_id:
            await interaction.response.send_message("Este panel pertenece a otra persona.", ephemeral=True)
            return False
        return True


class StatAmountButton(discord.ui.Button):
    def __init__(self, amount: int, label: str, style=discord.ButtonStyle.success):
        super().__init__(label=label[:80], style=style)
        self.amount = amount

    async def callback(self, interaction: discord.Interaction):
        view: StatQuantityView = self.view
        if view.done:
            await interaction.response.send_message("Este panel ya se usó.", ephemeral=True)
            return
        view.done = True
        await _apply_and_show(interaction, view.owner_id, view.stat, self.amount)


class StatAmountModal(GuildModal, title="Puntos a invertir"):
    cantidad = discord.ui.TextInput(label="¿Cuántos puntos?", placeholder="Ej: 7", min_length=1, max_length=14)

    def __init__(self, parent_view: "StatQuantityView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.cantidad.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Escribe un número válido.", ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
            return
        if amount > ADDPUNTOS_MAX:
            await interaction.response.send_message(
                f"❌ El máximo por uso es **{ADDPUNTOS_MAX:,}** puntos.", ephemeral=True)
            return
        if self.parent_view.done:
            await interaction.response.send_message("Este panel ya se usó.", ephemeral=True)
            return
        self.parent_view.done = True
        await _apply_and_show(interaction, self.parent_view.owner_id, self.parent_view.stat, amount)


class StatCustomButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Otra cantidad…", style=discord.ButtonStyle.primary, emoji="✏️")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(StatAmountModal(self.view))


class StatBackButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Volver", style=discord.ButtonStyle.secondary, emoji="↩️")

    async def callback(self, interaction: discord.Interaction):
        owner_id = self.view.owner_id
        embed, error, _s = await points_panel_embed(owner_id)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        await interaction.response.edit_message(embed=embed, view=StatPanelView(owner_id))


class StatQuantityView(GuildView):
    def __init__(self, owner_id: str, stat: str, points: int):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.stat = stat
        self.done = False
        _emoji, label, _col, per = STAT_INFO[stat]
        amounts = [n for n in (1, 5, 10) if n <= points]
        for n in amounts:
            self.add_item(StatAmountButton(n, f"{n} pt → +{n * per}"))
        if points > 1 and points not in amounts:
            self.add_item(StatAmountButton(points, f"Todos ({points}) → +{points * per}", discord.ButtonStyle.danger))
        if points > 1:
            self.add_item(StatCustomButton())
        self.add_item(StatBackButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.owner_id:
            await interaction.response.send_message("Este panel pertenece a otra persona.", ephemeral=True)
            return False
        return True


@tree.command(name="addpuntos", description="Mejora los stats de tu luchador: elige con el panel o escribe todo")
@app_commands.describe(
    stat="Estadística a mejorar (elige de la lista); vacío = abrir el panel",
    cantidad="Cuántos puntos invertir; vacío = elegir con botones",
)
async def addpuntos_slash(
    interaction: discord.Interaction,
    stat: str | None = None,
    cantidad: _Optional[app_commands.Range[int, 1, ADDPUNTOS_MAX]] = None,
):
    user_id = str(interaction.user.id)
    key = resolve_stat(stat) if stat else None
    embed, error, s = await points_panel_embed(user_id)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    if key is None:
        note = f"❌ No encontré la estadística **{stat}**. Elige una en el panel:" if stat else None
        await interaction.response.send_message(
            note, embed=embed, view=StatPanelView(user_id), ephemeral=True
        )
        return
    if cantidad is None:
        if s["points"] <= 0:
            await interaction.response.send_message("❌ No tienes puntos disponibles.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=stat_quantity_embed(key, s["points"]),
            view=StatQuantityView(user_id, key, s["points"]),
            ephemeral=True,
        )
        return
    result, error, _left = await apply_stat_points(user_id, key, cantidad)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    await interaction.response.send_message(embed=result)


addpuntos_slash.autocomplete("stat")(stat_autocomplete)


@tree.command(name="ftorneo", description="Crea un torneo de luchadores (con apuesta de entrada opcional)")
@app_commands.describe(apuesta="Entrada por jugador (acepta 5m, 500k). Sin apuesta, el campeón gana 60 millones")
async def ftorneo_slash(interaction: discord.Interaction, apuesta: str = "0"):
    uid = str(interaction.user.id)
    entry_fee = loan_parse_amount(apuesta)
    if entry_fee is None or entry_fee < 0:
        await interaction.response.send_message("❌ La apuesta debe ser un número válido (`5m`, `500k`...).", ephemeral=True)
        return
    await interaction.response.defer()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT fighter_id FROM fighters WHERE user_id = ?", (uid,)) as cur:
            row = await cur.fetchone()
    if not row:
        await interaction.followup.send("❌ Necesitas un luchador para organizar un torneo. Compra uno con `/buyfighter`.", ephemeral=True)
        return
    charge_error = await ftorneo_charge_host(uid, entry_fee)
    if charge_error:
        await interaction.followup.send(charge_error, ephemeral=True)
        return
    view = FighterTournamentView(host_id=uid, host_name=interaction.user.display_name, entry_fee=entry_fee)
    view.players.append((uid, interaction.user.display_name, row[0]))
    msg = await interaction.followup.send(embed=view.make_embed(), view=view)
    view.message = msg


@tree.command(name="addlevel", description="[ADMIN] Sube niveles al luchador de un usuario")
@app_commands.describe(usuario="El usuario objetivo", fighter_id="ID del luchador (ej: novato)", niveles="Cantidad de niveles a subir")
@app_commands.default_permissions(administrator=True)
async def addlevel_slash(interaction: discord.Interaction, usuario: discord.Member, fighter_id: str, niveles: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Solo los administradores pueden usar este comando.", ephemeral=True)
        return
    fid = fighter_id.lower().strip()
    if fid not in FIGHTERS:
        ids = ", ".join(f"`{k}`" for k in FIGHTERS)
        await interaction.response.send_message(f"❌ ID inválido. IDs válidos: {ids}", ephemeral=True)
        return
    if niveles <= 0:
        await interaction.response.send_message("❌ Debes agregar al menos 1 nivel.", ephemeral=True)
        return
    await interaction.response.defer()
    target_id = str(usuario.id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT fighter_id FROM fighters WHERE user_id=?", (target_id,)) as cur:
            frow = await cur.fetchone()
    if not frow:
        await interaction.followup.send(f"❌ **{usuario.name}** no tiene ningún luchador comprado.", ephemeral=True)
        return
    if frow[0] != fid:
        await interaction.followup.send(f"❌ **{usuario.name}** tiene un **{FIGHTERS[frow[0]]['name']}**, no un **{FIGHTERS[fid]['name']}**.", ephemeral=True)
        return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT level, xp, points FROM fighter_levels WHERE user_id=? AND fighter_id=?", (target_id, fid)) as cur:
            lvl_row = await cur.fetchone()
    cur_level, cur_xp, cur_points = lvl_row if lvl_row else (1, 0, 0)
    new_level = cur_level + niveles
    points_gained = niveles * 5
    new_points = cur_points + points_gained
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO fighter_levels (user_id, fighter_id, level, xp, points) VALUES (?,?,?,?,?) "
            "ON CONFLICT(user_id, fighter_id) DO UPDATE SET level=excluded.level, xp=excluded.xp, points=excluded.points",
            (target_id, fid, new_level, 0, new_points)
        )
        await db.commit()
    f = FIGHTERS[fid]
    embed = discord.Embed(title="🆙 ¡Niveles Añadidos!", color=0x00FF88)
    embed.description = (
        f"Se añadieron **{niveles}** niveles al luchador **{f['name']}** de {usuario.mention}\n\n"
        f"📊 Nivel anterior: **{cur_level}** → Nivel nuevo: **{new_level}**\n"
        f"🎯 Puntos ganados: **+{points_gained}** (total disponible: **{new_points}**)\n\n"
        f"_Por: {interaction.user.display_name}_"
    )
    await interaction.followup.send(embed=embed)


# ───────────────────────────── RULETA EN VIVO ─────────────────────────────

_LIVE_BET_ALIASES = {
    "red": "red", "rojo": "red",
    "black": "black", "negro": "black",
    "even": "even", "par": "even", "eleven": "even",
    "odd": "odd", "impar": "odd",
    "1st": "1st", "primera": "1st",
    "2nd": "2nd", "segunda": "2nd",
    "3rd": "3rd", "tercera": "3rd",
}

def _parse_live_bet_field(raw: str) -> tuple[int, str] | None:
    """Parse 'cantidad apuesta' string. Returns (amount, bet_key) or None."""
    parts = raw.lower().split()
    if len(parts) < 2:
        return None
    try:
        amt = int(parts[0])
    except ValueError:
        return None
    b = parts[1]
    if b in _LIVE_BET_ALIASES:
        return amt, _LIVE_BET_ALIASES[b]
    if b.isdigit() and 0 <= int(b) <= 36:
        return amt, b
    return None


class LiveBetModal(GuildModal, title="🎰 Tus Apuestas"):
    apuesta1 = discord.ui.TextInput(
        label="Apuesta 1",
        placeholder="ej: 1000 red  |  500 17  |  all even",
        required=True,
        max_length=30,
    )
    apuesta2 = discord.ui.TextInput(
        label="Apuesta 2 (opcional)",
        placeholder="ej: 200 black  |  300 1st",
        required=False,
        max_length=30,
    )
    apuesta3 = discord.ui.TextInput(
        label="Apuesta 3 (opcional)",
        placeholder="ej: 100 odd  |  50 0",
        required=False,
        max_length=30,
    )

    def __init__(self, live_view: "LiveRouletteView", bal: int):
        super().__init__()
        self._live_view = live_view
        self._bal = bal

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        bal = self._bal
        raw_fields = [self.apuesta1.value.strip(), self.apuesta2.value.strip(), self.apuesta3.value.strip()]
        slots: list[tuple[int, str]] = []

        for raw in raw_fields:
            if not raw:
                continue
            # support "all" as amount
            parts = raw.lower().split()
            if parts[0] == "all" and len(parts) >= 2:
                raw = f"{bal} {parts[1]}"
            parsed = _parse_live_bet_field(raw)
            if parsed is None:
                await interaction.response.send_message(
                    f"❌ Formato inválido: `{raw}`\nUsa `cantidad apuesta` — ej: `1000 red` · `500 17` · `200 even`",
                    ephemeral=True,
                )
                return
            amt, bk = parsed
            if amt <= 0:
                await interaction.response.send_message("❌ Las apuestas deben ser mayores a 0.", ephemeral=True)
                return
            slots.append((amt, bk))

        if not slots:
            await interaction.response.send_message("❌ Debes hacer al menos una apuesta.", ephemeral=True)
            return

        total_cost = sum(a for a, _ in slots)
        if bal < total_cost:
            await interaction.response.send_message(
                f"❌ Saldo insuficiente. Necesitas **{total_cost:,}** 🪙, tienes **{bal:,}** 🪙.",
                ephemeral=True,
            )
            return

        # Reserve funds immediately
        await update_balance(user_id, -total_cost)
        self._live_view.player_bets[user_id] = (interaction.user.display_name, slots, total_cost)

        await interaction.response.send_message(
            f"✅ **{total_cost:,}** 🪙 reservados. ¡Espera el giro!", ephemeral=True
        )
        await self._live_view.refresh_embed()


class LiveRouletteView(GuildView):
    MAX_PLAYERS = 10

    def __init__(self, host_id: str, host_name: str, timeout_secs: int = 60):
        super().__init__(timeout=float(timeout_secs))
        self.host_id = host_id
        self.host_name = host_name
        self.timeout_secs = timeout_secs
        # uid → (display_name, slots, total_cost)
        self.player_bets: dict[str, tuple[str, list[tuple[int, str]], int]] = {}
        self.message: discord.Message | None = None
        self.spun = False

    def make_embed(self) -> discord.Embed:
        embed = discord.Embed(title="🎰 Ruleta en Vivo", color=0xE91E63)
        n = len(self.player_bets)
        embed.description = (
            f"**Anfitrión:** {self.host_name}\n"
            f"⏳ **{self.timeout_secs}s** para hacer tus apuestas\n\n"
            f"Pulsa **🎲 Apostar** para participar (hasta 3 apuestas).\n"
            f"Solo el anfitrión puede girar antes del tiempo."
        )
        if self.player_bets:
            lines = []
            for uid, (name, slots, total) in self.player_bets.items():
                bet_parts = []
                for amt, bk in slots:
                    _, _, disp = evaluate_roulette_bet(1, bk)  # dummy numero≠0
                    bet_parts.append(f"{amt:,} {disp}")
                lines.append(f"🎯 **{name}** — {total:,} 🪙 → " + " · ".join(bet_parts))
            embed.add_field(
                name=f"👥 Jugadores ({n}/{self.MAX_PLAYERS})",
                value="\n".join(lines),
                inline=False,
            )
        else:
            embed.add_field(name="👥 Jugadores (0)", value="_Nadie ha apostado aún..._", inline=False)
        return embed

    async def refresh_embed(self):
        if self.message:
            try:
                await self.message.edit(embed=self.make_embed(), view=self)
            except Exception:
                pass

    @discord.ui.button(label="🎲 Apostar", style=discord.ButtonStyle.primary, emoji="🎲")
    async def bet_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.spun:
            await interaction.response.send_message("❌ La ruleta ya fue girada.", ephemeral=True)
            return
        uid = str(interaction.user.id)
        if uid in self.player_bets:
            await interaction.response.send_message("✅ Ya tienes apuestas registradas en este spin.", ephemeral=True)
            return
        if len(self.player_bets) >= self.MAX_PLAYERS:
            await interaction.response.send_message("❌ Mesa llena (máx. 10 jugadores).", ephemeral=True)
            return
        await get_or_create_user(uid, interaction.user.name)
        bal = await get_balance(uid)
        if bal <= 0:
            await interaction.response.send_message("❌ No tienes saldo para apostar.", ephemeral=True)
            return
        modal = LiveBetModal(self, bal)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🎰 Girar ahora", style=discord.ButtonStyle.danger, emoji="🎰")
    async def spin_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if str(interaction.user.id) != self.host_id:
            await interaction.response.send_message("❌ Solo el anfitrión puede girar.", ephemeral=True)
            return
        if self.spun:
            await interaction.response.send_message("❌ Ya fue girada.", ephemeral=True)
            return
        if not self.player_bets:
            await interaction.response.send_message("❌ Nadie ha apostado todavía.", ephemeral=True)
            return
        await interaction.response.defer()
        await self._do_spin()

    async def on_timeout(self):
        if self.spun:
            return
        if self.player_bets:
            await self._do_spin()
        else:
            for item in self.children:
                item.disabled = True
            if self.message:
                embed = discord.Embed(title="🎰 Ruleta en Vivo — Cancelada", color=0x888888)
                embed.description = "⏰ Tiempo agotado sin participantes."
                try:
                    await self.message.edit(embed=embed, view=self)
                except Exception:
                    pass

    async def _do_spin(self):
        self.spun = True
        for item in self.children:
            item.disabled = True

        resultado = random.randint(0, 36)
        num_emoji = "🟢" if resultado == 0 else ("🔴" if resultado in RED_NUMBERS else "⚫")

        jackpot = False
        player_lines = []

        for uid, (name, slots, total_staked) in self.player_bets.items():
            credit = 0
            lines = []
            for amt, bk in slots:
                won, mult, disp = evaluate_roulette_bet(resultado, bk)
                if won:
                    payout = amt + amt * mult
                    credit += payout
                    lines.append(f"  {disp} — {amt:,} → ✅ **+{amt*mult:,}** (x{mult})")
                    if mult == 35:
                        jackpot = True
                else:
                    lines.append(f"  {disp} — {amt:,} → ❌")

            if credit > 0:
                await update_balance(uid, credit)
            await track_mission(uid, "roulette_played")
            await log_bet(uid, "🎰 Ruleta Viva", total_staked, credit - total_staked)

            true_net = credit - total_staked
            net_str = f"+{true_net:,}" if true_net >= 0 else f"{true_net:,}"
            net_icon = "💰" if true_net >= 0 else "💸"
            player_lines.append(f"**{name}**\n" + "\n".join(lines) + f"\n{net_icon} Neto: **{net_str}** 🪙")

        color = 0xFFD700 if jackpot else 0x00FF88 if any(
            sum(
                (amt * mult if evaluate_roulette_bet(resultado, bk)[0] else -amt)
                for amt, bk in slots
            ) > 0
            for _, (_, slots, _) in self.player_bets.items()
        ) else 0xFF4444

        embed = discord.Embed(title=f"🎰 Ruleta en Vivo — ¡Resultado!", color=color)
        embed.description = f"## {num_emoji} **Número {resultado}**\n\n" + "\n\n".join(player_lines)
        embed.set_footer(text=f"🎰 {len(self.player_bets)} jugadores • Anfitrión: {self.host_name}")

        if self.message:
            try:
                await self.message.edit(embed=embed, view=self)
            except Exception:
                pass


def resolve_pack(text: str) -> str | None:
    key = _PACK_ALIASES.get(str(text).lower().strip())
    if key:
        return key
    p = _plain(text)
    if not p:
        return None
    for k, pt in PACK_TYPES.items():
        label = _plain(pt["label"])
        if p in (_plain(k), label, label.replace("sobre ", "", 1)):
            return k
    found = [k for k, pt in PACK_TYPES.items() if p in _plain(pt["label"])]
    return found[0] if len(found) == 1 else None


async def pack_autocomplete(interaction: discord.Interaction, current: str):
    p = _plain(current)
    out = []
    for k, pt in PACK_TYPES.items():
        if p and p not in f"{_plain(pt['label'])} {_plain(k)}":
            continue
        name = f"{pt['emoji']} {pt['label']} — {pt['price']:,} 🪙 · {CARDS_PER_PACK} cartas"
        out.append(app_commands.Choice(name=name[:100], value=k))
    return out[:25]


MAX_PACKS = 10


async def _do_pack_purchase(user, pack_key: str, cantidad: int = 1):
    from collections import Counter
    pt = PACK_TYPES[pack_key]
    cantidad = max(1, min(int(cantidad), MAX_PACKS))
    total = pt["price"] * cantidad
    user_id = str(user.id)
    await get_or_create_user(user_id, user.name)
    bal = await get_balance(user_id)
    if bal < total:
        embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
        embed.description = (
            f"{cantidad}x {pt['emoji']} **{pt['label']}** cuesta **{total:,}** 🪙. "
            f"Tienes **{bal:,}** 🪙."
        )
        return embed, False
    await update_balance(user_id, -total)
    drawn = []
    for _ in range(cantidad):
        drawn.extend(_draw_pack_cards(pack_key))
    for cid in drawn:
        await _add_card(user_id, cid)
    best_rarity = min((FOOTBALL_CARDS[c]["rarity"] for c in drawn),
                      key=lambda r: RARITY_CONFIG[r]["weight"])
    rc = RARITY_CONFIG[best_rarity]
    title = (f"{rc['emoji']} {pt['label']} — ¡{rc['label']}!" if rc["weight"] <= 4
             else f"{pt['emoji']} {pt['label']} abierto")
    embed = discord.Embed(title=title, color=rc["color"])
    if cantidad == 1:
        lines = [f"➤ {_card_line(c)}" for c in drawn]
        intro = f"**{user.display_name}** abrió un **{pt['label']}** y obtuvo:\n\n"
    else:
        counts = Counter(drawn)
        ordered = sorted(counts, key=lambda c: -FOOTBALL_CARDS[c]["ovr"])
        lines = [f"➤ {_card_line(c, counts[c])}" for c in ordered]
        intro = f"**{user.display_name}** abrió **{cantidad}x {pt['label']}** y obtuvo:\n\n"
    embed.description = (intro + "\n".join(lines))[:4000]
    new_bal = await get_balance(user_id)
    embed.set_footer(text=f"💸 Gastaste {total:,} 🪙 · 💰 Saldo restante: {new_bal:,} 🪙")
    return embed, True


async def _open_card_pack(
    interaction: discord.Interaction, tipo: str, *, ephemeral: bool = False, cantidad: int = 1
):
    pack_key = resolve_pack(tipo)
    if not pack_key:
        lines = "\n".join(
            f"{pt['emoji']} `{k}` — {pt['label']} · **{pt['price']:,}** 🪙"
            for k, pt in PACK_TYPES.items()
        )
        embed = discord.Embed(title="❌ Tipo de sobre inválido", color=0xFF4444,
                              description=f"Tipos disponibles:\n{lines}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    await interaction.response.defer(ephemeral=ephemeral)
    embed, _ok = await _do_pack_purchase(interaction.user, pack_key, cantidad)
    await interaction.followup.send(embed=embed, ephemeral=ephemeral or not _ok)


class FootballPackSelect(discord.ui.Select):
    def __init__(self, owner_id: str):
        self.owner_id = owner_id
        options = [
            discord.SelectOption(
                label=f"{pack['label']} · {pack['price']:,} monedas",
                value=pack_id,
                description=f"{CARDS_PER_PACK} cartas · {len(FOOTBALL_CARDS)} en la colección",
                emoji=pack["emoji"],
            )
            for pack_id, pack in PACK_TYPES.items()
        ]
        super().__init__(
            placeholder="Elige un sobre para comprar y abrir",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.owner_id:
            await interaction.response.send_message(
                "Este panel pertenece a otra persona.", ephemeral=True
            )
            return
        view = self.view
        if view is None or view.purchase_completed:
            await interaction.response.send_message(
                "Este panel ya fue utilizado. Ejecuta `/infocartas` para abrir otro.",
                ephemeral=True,
            )
            return
        view.purchase_completed = True
        await _open_card_pack(interaction, self.values[0], ephemeral=True)
        try:
            if interaction.message:
                await interaction.message.edit(view=None)
        except discord.HTTPException:
            pass


class FootballPackStoreView(GuildView):
    def __init__(self, owner_id: str):
        super().__init__(timeout=180)
        self.purchase_completed = False
        self.add_item(FootballPackSelect(owner_id))


@tree.command(name="abrirpaquete", description="Compra y abre sobres de tarjetas de fútbol")
@app_commands.describe(
    tipo="Elige el sobre de la lista",
    cantidad=f"Cuántos sobres abrir (1-{MAX_PACKS}, por defecto 1)",
)
async def abrirpaquete_slash(
    interaction: discord.Interaction,
    tipo: str = "comun",
    cantidad: app_commands.Range[int, 1, 10] = 1,
):
    await _open_card_pack(interaction, tipo, cantidad=cantidad)


abrirpaquete_slash.autocomplete("tipo")(pack_autocomplete)


@tree.command(name="comprarsobre", description="Compra y abre sobres de tarjetas de fútbol")
@app_commands.describe(
    tipo="Elige el sobre de la lista",
    cantidad=f"Cuántos sobres abrir (1-{MAX_PACKS}, por defecto 1)",
)
async def comprarsobre_slash(
    interaction: discord.Interaction,
    tipo: str,
    cantidad: app_commands.Range[int, 1, 10] = 1,
):
    await _open_card_pack(interaction, tipo, cantidad=cantidad)


comprarsobre_slash.autocomplete("tipo")(pack_autocomplete)


async def _send_card_collection(
    interaction: discord.Interaction,
    target: discord.Member | discord.User,
    title_prefix: str = "Colección",
):
    target_id = str(target.id)
    is_own = target_id == str(interaction.user.id)
    await get_or_create_user(target_id, target.name)
    rows = await _get_collection(target_id)
    if not rows:
        embed = discord.Embed(title="📦 Inventario de cartas vacío", color=0x95A5A6)
        if is_own:
            embed.description = "Aún no tienes tarjetas. Usa `/comprarsobre` para conseguir las primeras."
        else:
            embed.description = f"**{target.display_name}** aún no tiene tarjetas."
        await interaction.response.send_message(embed=embed)
        return
    by_rarity: dict[str, list[tuple[str, int]]] = {r: [] for r in RARITY_CONFIG}
    total_cards = sum(q for _, q in rows)
    unique_cards = len(rows)
    best_card_id = max(
        (cid for cid, _ in rows if cid in FOOTBALL_CARDS),
        key=lambda cid: FOOTBALL_CARDS[cid]["ovr"],
        default=None,
    )
    for cid, qty in rows:
        card = FOOTBALL_CARDS.get(cid)
        if card:
            by_rarity[card["rarity"]].append((cid, qty))
    best_rarity_owned = next(
        (rarity for rarity in RARITY_CONFIG if by_rarity[rarity]), "comun"
    )
    embed = discord.Embed(
        title=f"⚽ {title_prefix} de {target.display_name}",
        color=RARITY_CONFIG[best_rarity_owned]["color"],
    )
    summary = f"🃏 **{unique_cards}** únicas · **{total_cards}** total"
    if best_card_id:
        best_card = FOOTBALL_CARDS[best_card_id]
        summary += (
            f"\n⭐ Mejor carta: {RARITY_CONFIG[best_card['rarity']]['emoji']} "
            f"**{best_card['name']}** OVR {best_card['ovr']}"
        )
    embed.description = summary + "\n\u200b"
    for rarity in RARITY_CONFIG:
        cards = by_rarity[rarity]
        if not cards:
            continue
        rarity_config = RARITY_CONFIG[rarity]
        sorted_cards = sorted(cards, key=lambda item: -FOOTBALL_CARDS[item[0]]["ovr"])
        embed.add_field(
            name=f"{rarity_config['emoji']} {rarity_config['label']} ({len(cards)})",
            value="\n".join(_card_line(card_id, quantity) for card_id, quantity in sorted_cards),
            inline=False,
        )
    if not is_own:
        embed.set_footer(text=f"💡 Usa /intercambiar {target.display_name} para proponer un intercambio")
    await interaction.response.send_message(embed=embed)


@tree.command(name="coleccion", description="Muestra la colección de tarjetas de fútbol (tuya o de otro jugador)")
@app_commands.describe(usuario="El jugador cuya colección quieres ver (deja vacío para la tuya)")
async def coleccion_slash(interaction: discord.Interaction, usuario: discord.Member | None = None):
    await _send_card_collection(interaction, usuario or interaction.user)


@tree.command(name="inventariocartas", description="Muestra tus cartas de fútbol y duplicados")
async def inventariocartas_slash(interaction: discord.Interaction):
    await _send_card_collection(interaction, interaction.user, "Inventario de cartas")


@tree.command(name="infocartas", description="Muestra los tipos de sobres, precios y probabilidades")
async def infocartas_slash(interaction: discord.Interaction):
    embed = discord.Embed(title="⚽ Sobres de Tarjetas de Fútbol", color=0x3498DB)
    embed.description = (
        f"📦 **{CARDS_PER_PACK} cartas** por sobre · **{len(FOOTBALL_CARDS)} cartas** en total\n"
        "🎲 Porcentajes por carta; las tres se sortean independientemente. No hay rarezas garantizadas.\n"
    )
    for pack_key, pt in PACK_TYPES.items():
        embed.add_field(
            name=f"{pt['emoji']} {pt['label']} — {pt['price']:,} 🪙",
            value=_format_pack_probabilities(pt),
            inline=False,
        )
    embed.set_footer(text="Elige un sobre en el menú o usa /comprarsobre.")
    await interaction.response.send_message(
        embed=embed,
        view=FootballPackStoreView(str(interaction.user.id)),
        ephemeral=True,
    )


# ─────────────────────────── MERCADO DE CARTAS ───────────────────────────

MAX_LISTINGS_PER_USER = 5


async def _market_listings(rarity_filter: str = "") -> list[tuple]:
    """Return open listings: (id, seller_id, card_id, price, ts)."""
    async with aiosqlite.connect(DB_PATH) as db:
        if rarity_filter:
            cards_in_rarity = [cid for cid, c in FOOTBALL_CARDS.items()
                               if c["rarity"] == rarity_filter]
            placeholders = ",".join("?" for _ in cards_in_rarity)
            if not placeholders:
                return []
            async with db.execute(
                f"SELECT id, seller_id, card_id, price, ts FROM card_market "
                f"WHERE card_id IN ({placeholders}) ORDER BY price ASC LIMIT 20",
                cards_in_rarity
            ) as cur:
                return await cur.fetchall()
        async with db.execute(
            "SELECT id, seller_id, card_id, price, ts FROM card_market ORDER BY price ASC LIMIT 20"
        ) as cur:
            return await cur.fetchall()


async def _market_count_seller(seller_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM card_market WHERE seller_id=?", (seller_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def _market_get_listing(listing_id: int) -> tuple | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, seller_id, card_id, price, ts FROM card_market WHERE id=?",
            (listing_id,)
        ) as cur:
            return await cur.fetchone()


async def _market_delete_listing(listing_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM card_market WHERE id=?", (listing_id,))
        await db.commit()


def _market_embed(listings: list[tuple], title: str, footer: str = "") -> discord.Embed:
    embed = discord.Embed(title=title, color=0xF39C12)
    if not listings:
        embed.description = "No hay cartas en venta ahora mismo. ¡Sé el primero en publicar una!"
        return embed
    lines = []
    for lid, seller_id, card_id, price, ts in listings:
        c = FOOTBALL_CARDS.get(card_id, {})
        rc = RARITY_CONFIG.get(c.get("rarity", "comun"), RARITY_CONFIG["comun"])
        lines.append(
            f"`#{lid}` {rc['emoji']} **{c.get('name','?')}** `{c.get('pos','?')}` "
            f"— **{price:,}** 🪙"
        )
    embed.description = "\n".join(lines)
    if footer:
        embed.set_footer(text=footer)
    return embed


MARKET_PURCHASE_LOCKS: dict[int, asyncio.Lock] = {}


async def complete_market_purchase(
    user: discord.User | discord.Member, listing_id: int
) -> tuple[discord.Embed | None, str | None]:
    lock = MARKET_PURCHASE_LOCKS.setdefault(listing_id, asyncio.Lock())
    async with lock:
        user_id = str(user.id)
        await get_or_create_user(user_id, user.name)
        listing = await _market_get_listing(listing_id)
        if not listing:
            return None, f"La publicación **#{listing_id}** no existe o ya fue vendida."

        lid, seller_id, card_id, price, _ = listing
        if seller_id == user_id:
            return None, "No puedes comprar tu propia carta."

        balance = await get_balance(user_id)
        if balance < price:
            return None, f"Necesitas **{price:,}** 🪙 pero tienes **{balance:,}** 🪙."

        await _market_delete_listing(lid)
        await update_balance(user_id, -price)
        await update_balance(seller_id, price)
        await _add_card(user_id, card_id)
        new_balance = await get_balance(user_id)

    card = FOOTBALL_CARDS[card_id]
    rarity = RARITY_CONFIG[card["rarity"]]
    embed = discord.Embed(title="🎉 ¡Compra exitosa!", color=rarity["color"])
    embed.description = (
        f"➤ {_card_line(card_id)}\n\n"
        f"💸 Pagaste: **{price:,}** 🪙\n"
        "La carta fue añadida a tu colección."
    )
    embed.set_footer(text=f"Saldo restante: {new_balance:,} 🪙")

    try:
        seller = await client.fetch_user(int(seller_id))
        dm_embed = discord.Embed(title="💰 ¡Vendiste una carta!", color=0x2ECC71)
        dm_embed.description = (
            f"**{user.display_name}** compró tu:\n"
            f"➤ {_card_line(card_id)}\n\n"
            f"Recibiste **{price:,}** 🪙 en tu balance."
        )
        await seller.send(embed=dm_embed)
    except Exception:
        pass
    return embed, None


async def cancel_market_listing(
    seller_id: str, listing_id: int
) -> tuple[str | None, str | None]:
    lock = MARKET_PURCHASE_LOCKS.setdefault(listing_id, asyncio.Lock())
    async with lock:
        listing = await _market_get_listing(listing_id)
        if not listing:
            return None, f"La publicación **#{listing_id}** no existe."
        lid, owner_id, card_id, _price, _timestamp = listing
        if owner_id != seller_id:
            return None, "Esa publicación no es tuya."
        await _market_delete_listing(lid)
        await _add_card(seller_id, card_id)
        return card_id, None


class MarketBuySelect(discord.ui.Select):
    def __init__(self, listings: list[tuple], rarity_filter: str = ""):
        self.rarity_filter = rarity_filter
        options = []
        for listing_id, _seller_id, card_id, price, _ts in listings[:25]:
            card = FOOTBALL_CARDS.get(card_id, {})
            rarity = RARITY_CONFIG.get(
                card.get("rarity", "comun"), RARITY_CONFIG["comun"]
            )
            options.append(
                discord.SelectOption(
                    label=f"#{listing_id} {card.get('name', card_id)} · {price:,} 🪙"[:100],
                    value=str(listing_id),
                    description=f"{rarity['label']} · comprar esta publicación"[:100],
                    emoji=rarity["emoji"],
                )
            )
        super().__init__(
            placeholder="Elige una carta para comprar",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed, error = await complete_market_purchase(
            interaction.user, int(self.values[0])
        )
        view = self.view
        if isinstance(view, MarketBuyView) and interaction.message:
            refreshed_listings = await _market_listings(view.rarity_filter)
            view.clear_items()
            if refreshed_listings:
                view.add_item(
                    MarketBuySelect(refreshed_listings, view.rarity_filter)
                )
                updated_view = view
            else:
                view.stop()
                updated_view = None
            try:
                await interaction.message.edit(
                    embed=build_market_store_embed(
                        refreshed_listings, view.rarity_filter
                    ),
                    view=updated_view,
                )
            except discord.HTTPException:
                pass
        if error:
            await interaction.followup.send(error, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)


class MarketBuyView(GuildView):
    def __init__(self, listings: list[tuple], rarity_filter: str = ""):
        super().__init__(timeout=180)
        self.rarity_filter = rarity_filter
        self.add_item(MarketBuySelect(listings, rarity_filter))


def build_market_store_embed(
    listings: list[tuple], rarity_filter: str = ""
) -> discord.Embed:
    title = "🏪 Mercado de Cartas"
    if rarity_filter:
        rarity = RARITY_CONFIG[rarity_filter]
        title += f" — {rarity['emoji']} {rarity['label']}"
    embed = _market_embed(listings, title)
    footer = (
        "Elige una carta del menú para comprar · /vender <carta> <precio>"
        if listings
        else "No hay publicaciones disponibles ahora mismo."
    )
    embed.set_footer(text=footer)
    return embed


@tree.command(name="vender", description="Publica una carta en el mercado para que otros la compren")
@app_commands.describe(
    carta="ID de la carta a vender (ej: messi, pele, cr7)",
    precio="Precio en monedas (mínimo 100)"
)
async def vender_slash(interaction: discord.Interaction, carta: str, precio: int):
    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)
    carta = carta.strip().lower()
    if carta not in FOOTBALL_CARDS:
        await interaction.response.send_message(f"❌ Carta `{carta}` no existe.", ephemeral=True)
        return
    if precio < 100:
        await interaction.response.send_message("❌ El precio mínimo es **100** 🪙.", ephemeral=True)
        return
    qty = await _card_qty(user_id, carta)
    if qty < 1:
        c = FOOTBALL_CARDS[carta]
        await interaction.response.send_message(
            f"❌ No tienes la carta **{c['name']}**.", ephemeral=True)
        return
    count = await _market_count_seller(user_id)
    if count >= MAX_LISTINGS_PER_USER:
        await interaction.response.send_message(
            f"❌ Ya tienes **{MAX_LISTINGS_PER_USER}** cartas en venta. Cancela alguna primero.",
            ephemeral=True)
        return
    # Escrow: remove from collection, add to market
    await _remove_card(user_id, carta)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO card_market (seller_id, card_id, price, ts) VALUES (?,?,?,?)",
            (user_id, carta, precio, datetime.utcnow().isoformat())
        )
        await db.commit()
    c = FOOTBALL_CARDS[carta]
    rc = RARITY_CONFIG[c["rarity"]]
    embed = discord.Embed(title="🏪 ¡Carta publicada!", color=rc["color"])
    embed.description = (
        f"➤ {_card_line(carta)}\n\n"
        f"💰 Precio: **{precio:,}** 🪙\n"
        f"La carta fue retirada de tu colección hasta que se venda o la canceles."
    )
    embed.set_footer(text="Usa /cancelarventa <id> para retirarla del mercado")
    await interaction.response.send_message(embed=embed)


@tree.command(name="mercado", description="Explora las cartas en venta")
@app_commands.describe(rareza="Filtrar por rareza: comun / poco_comun / raro / epico / legendario")
async def mercado_slash(interaction: discord.Interaction, rareza: str = ""):
    rarity_key = _PACK_ALIASES.get(rareza.lower().strip(), "") if rareza else ""
    listings = await _market_listings(rarity_key)
    embed = build_market_store_embed(listings, rarity_key)
    view = MarketBuyView(listings, rarity_key) if listings else None
    await interaction.response.send_message(embed=embed, view=view)


@tree.command(name="comprar", description="Compra una carta del mercado")
@app_commands.describe(id="Número de la publicación (el #id que aparece en /mercado)")
async def comprar_slash(interaction: discord.Interaction, id: int):
    await interaction.response.defer(ephemeral=True)
    embed, error = await complete_market_purchase(interaction.user, id)
    if error:
        await interaction.followup.send(error, ephemeral=True)
    else:
        await interaction.followup.send(embed=embed, ephemeral=True)


@tree.command(name="cancelarventa", description="Retira tu carta del mercado y devuélvela a tu colección")
@app_commands.describe(id="Número de la publicación a cancelar")
async def cancelarventa_slash(interaction: discord.Interaction, id: int):
    user_id = str(interaction.user.id)
    card_id, error = await cancel_market_listing(user_id, id)
    if error:
        await interaction.response.send_message(f"❌ {error}", ephemeral=True)
        return
    embed = discord.Embed(title="↩️ Venta cancelada", color=0x95A5A6)
    embed.description = f"➤ {_card_line(card_id)}\n\nLa carta fue devuelta a tu colección."
    await interaction.response.send_message(embed=embed)


@tree.command(name="misventas", description="Muestra tus cartas actualmente en venta")
async def misventas_slash(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, card_id, price, ts FROM card_market WHERE seller_id=? ORDER BY id",
            (user_id,)
        ) as cur:
            rows = await cur.fetchall()
    if not rows:
        embed = discord.Embed(title="📦 Sin ventas activas", color=0x95A5A6,
                               description="No tienes cartas en el mercado.\nUsa `/vender <carta> <precio>` para publicar una.")
        await interaction.response.send_message(embed=embed)
        return
    embed = discord.Embed(title="🏷️ Mis cartas en venta", color=0xF39C12)
    lines = []
    for lid, card_id, price, ts in rows:
        c = FOOTBALL_CARDS.get(card_id, {})
        rc = RARITY_CONFIG.get(c.get("rarity", "comun"), RARITY_CONFIG["comun"])
        lines.append(f"`#{lid}` {rc['emoji']} **{c.get('name','?')}** — **{price:,}** 🪙")
    embed.description = "\n".join(lines)
    embed.set_footer(text=f"{len(rows)}/{MAX_LISTINGS_PER_USER} slots usados · /cancelarventa <id> para retirar")
    await interaction.response.send_message(embed=embed)


# ─────────────────────────────────────────────────────────────────────────

class TradeView(GuildView):
    """Accept/Decline buttons for a card trade proposal."""

    def __init__(self, from_uid: str, to_uid: str,
                 from_card: str, to_card: str,
                 from_name: str, to_name: str):
        super().__init__(timeout=300)
        self.from_uid   = from_uid
        self.to_uid     = to_uid
        self.from_card  = from_card   # card the proposer offers
        self.to_card    = to_card     # card the receiver offers back (may be "")
        self.from_name  = from_name
        self.to_name    = to_name
        self.done       = False

    @discord.ui.button(label="✅ Aceptar", style=discord.ButtonStyle.success)
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.to_uid:
            await interaction.response.send_message("❌ Esta oferta no es para ti.", ephemeral=True)
            return
        if self.done:
            await interaction.response.send_message("❌ Esta oferta ya fue procesada.", ephemeral=True)
            return
        self.done = True
        self.stop()
        # Verify cards still exist
        from_has = await _card_qty(self.from_uid, self.from_card)
        to_has   = await _card_qty(self.to_uid, self.to_card) if self.to_card else 1
        fc = FOOTBALL_CARDS.get(self.from_card, {})
        tc = FOOTBALL_CARDS.get(self.to_card, {}) if self.to_card else {}
        if from_has < 1:
            await interaction.response.edit_message(
                content=f"❌ **{self.from_name}** ya no tiene **{fc.get('name','?')}**. Intercambio cancelado.",
                embed=None, view=None)
            return
        if self.to_card and to_has < 1:
            await interaction.response.edit_message(
                content=f"❌ Ya no tienes **{tc.get('name','?')}**. Intercambio cancelado.",
                embed=None, view=None)
            return
        # Execute swap
        await _remove_card(self.from_uid, self.from_card)
        await _add_card(self.to_uid,   self.from_card)
        if self.to_card:
            await _remove_card(self.to_uid,   self.to_card)
            await _add_card(self.from_uid, self.to_card)
        # Build result embed
        rc_f = RARITY_CONFIG[fc["rarity"]]["emoji"]
        desc = f"✅ ¡Intercambio completado!\n\n"
        desc += f"**{self.from_name}** dio: {rc_f} **{fc['name']}**\n"
        if self.to_card:
            rc_t = RARITY_CONFIG[tc["rarity"]]["emoji"]
            desc += f"**{self.to_name}** dio: {rc_t} **{tc['name']}**"
        else:
            desc += f"**{self.to_name}** recibió la carta como regalo."
        embed = discord.Embed(title="🤝 Intercambio Exitoso", color=0x2ECC71, description=desc)
        await interaction.response.edit_message(embed=embed, view=None, content=None)

    @discord.ui.button(label="❌ Rechazar", style=discord.ButtonStyle.danger)
    async def decline_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.to_uid:
            await interaction.response.send_message("❌ Esta oferta no es para ti.", ephemeral=True)
            return
        if self.done:
            await interaction.response.send_message("❌ Esta oferta ya fue procesada.", ephemeral=True)
            return
        self.done = True
        self.stop()
        await interaction.response.edit_message(
            content=f"❌ **{self.to_name}** rechazó el intercambio.",
            embed=None, view=None)

    async def on_timeout(self):
        self.done = True
        for child in self.children:
            child.disabled = True  # type: ignore


@tree.command(name="intercambiar", description="Propone un intercambio de tarjetas con otro jugador")
@app_commands.describe(
    usuario="El jugador con quien intercambiar",
    mi_carta="ID de tu carta (ej: messi, pele, cr7)",
    su_carta="ID de la carta que pides a cambio (opcional — deja vacío para regalar)",
)
async def intercambiar_slash(interaction: discord.Interaction,
                              usuario: discord.Member,
                              mi_carta: str,
                              su_carta: str = ""):
    from_uid = str(interaction.user.id)
    to_uid   = str(usuario.id)
    if to_uid == from_uid:
        await interaction.response.send_message("❌ No puedes intercambiar contigo mismo.", ephemeral=True)
        return
    if usuario.bot:
        await interaction.response.send_message("❌ No puedes intercambiar con un bot.", ephemeral=True)
        return
    mi_carta  = mi_carta.strip().lower()
    su_carta  = su_carta.strip().lower()
    if mi_carta not in FOOTBALL_CARDS:
        await interaction.response.send_message(f"❌ Carta `{mi_carta}` no existe.", ephemeral=True)
        return
    if su_carta and su_carta not in FOOTBALL_CARDS:
        await interaction.response.send_message(f"❌ Carta `{su_carta}` no existe.", ephemeral=True)
        return
    await get_or_create_user(from_uid, interaction.user.name)
    await get_or_create_user(to_uid, usuario.name)
    my_qty = await _card_qty(from_uid, mi_carta)
    if my_qty < 1:
        await interaction.response.send_message(
            f"❌ No tienes la carta **{FOOTBALL_CARDS[mi_carta]['name']}**.", ephemeral=True)
        return
    if su_carta:
        their_qty = await _card_qty(to_uid, su_carta)
        if their_qty < 1:
            await interaction.response.send_message(
                f"❌ **{usuario.display_name}** no tiene la carta **{FOOTBALL_CARDS[su_carta]['name']}**.",
                ephemeral=True)
            return
    fc = FOOTBALL_CARDS[mi_carta]
    rc_f = RARITY_CONFIG[fc["rarity"]]
    desc  = f"**{interaction.user.display_name}** te ofrece:\n"
    desc += f"➤ {_card_line(mi_carta)}\n\n"
    if su_carta:
        tc = FOOTBALL_CARDS[su_carta]
        rc_t = RARITY_CONFIG[tc["rarity"]]
        desc += f"A cambio pide tu:\n➤ {_card_line(su_carta)}\n\n"
    else:
        desc += "_Sin pedir nada a cambio (regalo)_\n\n"
    desc += f"⏱️ Tienes **5 minutos** para responder."
    embed = discord.Embed(
        title=f"🤝 Propuesta de Intercambio para {usuario.display_name}",
        color=rc_f["color"], description=desc)
    view = TradeView(from_uid, to_uid, mi_carta, su_carta,
                     interaction.user.display_name, usuario.display_name)
    await interaction.response.send_message(
        content=f"{usuario.mention} tienes una oferta de intercambio:",
        embed=embed, view=view)


@tree.command(name="historial", description="Muestra tus últimas 10 apuestas con ganancias/pérdidas")
async def historial_slash(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT game, amount_bet, net, ts FROM bet_history WHERE user_id=? ORDER BY id DESC LIMIT 10",
            (user_id,)
        ) as cur:
            rows = await cur.fetchall()
        async with db.execute(
            "SELECT COUNT(*), SUM(amount_bet), SUM(net) FROM bet_history WHERE user_id=?",
            (user_id,)
        ) as cur:
            stats = await cur.fetchone()

    embed = discord.Embed(title=f"📊 Historial de {interaction.user.display_name}", color=0x3498DB)
    if not rows:
        embed.description = "No tienes apuestas registradas todavía.\nJuega a la ruleta o slots para empezar."
    else:
        lines = []
        for game, amount_bet, net, ts in rows:
            try:
                dt = datetime.fromisoformat(ts)
                date_str = dt.strftime("%d/%m %H:%M")
            except Exception:
                date_str = "—"
            icon = "✅" if net >= 0 else "❌"
            net_str = f"+{net:,}" if net >= 0 else f"{net:,}"
            lines.append(f"{icon} **{game}** — apostado: {amount_bet:,} 🪙 → **{net_str}** 🪙 _{date_str}_")
        embed.description = "\n".join(lines)

        total_games, total_wagered, total_net = stats
        total_wagered = total_wagered or 0
        total_net = total_net or 0
        net_color = "🟢" if total_net >= 0 else "🔴"
        total_net_str = f"+{total_net:,}" if total_net >= 0 else f"{total_net:,}"
        embed.add_field(
            name="📈 Estadísticas totales",
            value=(
                f"🎲 Partidas jugadas: **{total_games}**\n"
                f"💸 Total apostado: **{total_wagered:,}** 🪙\n"
                f"{net_color} Balance neto: **{total_net_str}** 🪙"
            ),
            inline=False,
        )
    await interaction.response.send_message(embed=embed)


@tree.command(name="ruleta-en-vivo", description="Abre una mesa de ruleta — todos apuestan y el resultado es colectivo")
@app_commands.describe(tiempo="Segundos para apostar (10-120, default 60)")
async def live_roulette_slash(interaction: discord.Interaction, tiempo: int = 60):
    if not (10 <= tiempo <= 120):
        await interaction.response.send_message("❌ El tiempo debe estar entre 10 y 120 segundos.", ephemeral=True)
        return
    host_id = str(interaction.user.id)
    await get_or_create_user(host_id, interaction.user.name)
    view = LiveRouletteView(host_id=host_id, host_name=interaction.user.display_name, timeout_secs=tiempo)
    embed = view.make_embed()
    await interaction.response.send_message(embed=embed, view=view)
    view.message = await interaction.original_response()


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if not message.content.startswith(PREFIX):
        return

    content = message.content[len(PREFIX):].strip()
    parts = content.split()
    if not parts:
        return

    cmd = parts[0].lower()
    args = parts[1:]
    user_id = str(message.author.id)

    if cmd == "blacklist":
        await blacklist_handle_prefix(message, args)
        return
    if not await enter_message(message, cmd):
        return

    if cmd == "clan":
        await clan_handle_prefix(message, args)
        return

    if await loan_handle_prefix(message, cmd, args):
        return
    if await role_loan_handle_prefix(message, cmd, args):
        return
    if await features_handle_prefix(message, cmd, args):
        return

    # ,bal [@usuario|ID]
    if cmd in ("bal", "balance", "saldo"):
        await send_prefix_balance(message, args)
        return

    # ,shop
    elif cmd == "shop":
        embed = discord.Embed(title="🏪 Tienda del Casino", color=0x9B59B6)
        embed.description = (
            "Usa `/buy` para abrir el panel de compra, `/buy <id_item>` o "
            "`,buy <id_item>` para comprar por ID. Los roles se cobran con `,collect`.\n"
        )
        categorias = {
            "proteccion": "🛡️ Protección",
            "rol": "👑 Roles del servidor · /use y /collect",
            "decorativo": "🎭 Decorativos",
        }
        for cat_key, cat_name in categorias.items():
            items_in_cat = [(k, v) for k, v in SHOP_ITEMS.items() if v["category"] == cat_key]
            if not items_in_cat:
                continue
            lines = [
                f"**{item['name']}** — {item['price']:,} 🪙\n{item['description']}\n`ID: {item_id}`"
                for item_id, item in items_in_cat
            ]
            embed.add_field(name=cat_name, value="\n\n".join(lines), inline=False)
        await message.channel.send(embed=embed, view=ShopBuyView(user_id))

    # ,collect
    elif cmd == "collect":
        await get_or_create_user(user_id, message.author.name)
        owned_roles, ready_roles, waiting_roles, borrowed, payouts, multiplier = await collect_available_role_earnings(user_id)

        if not owned_roles:
            embed = discord.Embed(title="❌ Sin Roles", color=0xFF4444)
            embed.description = (
                "No tienes ningún rol activo.\n"
                "Compra un rol con `,buy` para ganar monedas con `,collect`.\n\n"
                "🥉 **Bronce** — +50,000,000 🪙 cada 4h\n"
                "🥈 **Plata** — +60,000,000 🪙 cada 5h\n"
                "🥇 **Oro** — +70,000,000 🪙 cada 6h\n"
                "💎 **Diamante** — +160,000,000 🪙 cada 7h\n"
                "🔴 **Ruby** — +200,000,000 🪙 cada 8h\n"
                "🟢 **Esmeralda** — +250,000,000 🪙 cada 9h\n"
                "🔷 **Zafiro** — +350,000,000 🪙 cada 10h\n"
                "⚫ **Obsidiana** — +500,000,000 🪙 cada 11h"
            )
            await message.channel.send(embed=embed)
            return

        if not ready_roles:
            embed = discord.Embed(title="⏰ Ningún collect listo todavía", color=0xFFAA00)
            embed.description = "\n".join(
                f"{SHOP_ITEMS[role_id]['name']}: vuelve en **{format_collect_wait(next_collect)}**"
                for role_id, next_collect in waiting_roles
            )
            await message.channel.send(embed=embed)
            return

        total_bonus = sum(payouts[r] for r in ready_roles)

        event_note = f" · 🎉 evento x{multiplier}" if multiplier > 1 else ""
        new_balance = await get_balance(user_id)
        embed = discord.Embed(title="💰 ¡Ganancias Recogidas!", color=0x00FF88)
        lines = "\n".join(
            f"{SHOP_ITEMS[r]['name']}{f' (prestado · {ROLE_LOAN_LENDER_PERCENT}% para su dueño)' if r in borrowed else ''} "
            f"→ +**{payouts[r]:,}** 🪙"
            for r in ready_roles
        )
        embed.description = (
            f"{lines}\n\n"
            f"**Total:** +**{total_bonus:,}** 🪙{event_note}\n"
            f"Saldo actual: **{new_balance:,}** 🪙"
        )
        if waiting_roles:
            embed.add_field(
                name="⏳ Aún en espera",
                value="\n".join(
                    f"{SHOP_ITEMS[role_id]['name']}: **{format_collect_wait(next_collect)}**"
                    for role_id, next_collect in waiting_roles
                ),
                inline=False,
            )
        await message.channel.send(embed=embed)

    # ,roulette <cantidad|all> <red|rojo|black|negro>
    elif cmd == "roulette":
        await get_or_create_user(user_id, message.author.name)
        bal = await get_balance(user_id)

        ROULETTE_HELP = (
            "❌ Uso: `,roulette <cantidad|all> <apuesta> [cantidad2 apuesta2] ...`\n"
            "Apuestas: `red` `black` `even` `odd` `1st` `2nd` `3rd` o un número **0-36** (35:1)\n"
            "Hasta **5 apuestas** en el mismo spin:\n"
            "  `,roulette 1000 red 500 17 200 even`\n"
            "  `,roulette all 0   (todo al verde, 35:1)`"
        )
        BET_ALIASES = {
            "red": "red", "rojo": "red",
            "black": "black", "negro": "black",
            "even": "even", "par": "even", "eleven": "even",
            "odd": "odd", "impar": "odd",
            "1st": "1st", "primera": "1st",
            "2nd": "2nd", "segunda": "2nd",
            "3rd": "3rd", "tercera": "3rd",
        }

        if len(args) < 2:
            await message.channel.send(ROULETTE_HELP)
            return

        # Parse args as pairs: (amount, bet_key) — up to 5 bets
        slots: list[tuple[int, str]] = []
        i = 0
        parse_error = None
        while i < len(args) - 1 and len(slots) < 5:
            a_str = args[i].lower()
            b_str = args[i + 1].lower()
            if a_str == "all":
                amt = bal
            else:
                try:
                    amt = int(a_str)
                except ValueError:
                    parse_error = f"❌ `{a_str}` no es una cantidad válida."
                    break
            if b_str in BET_ALIASES:
                bk = BET_ALIASES[b_str]
            elif b_str.isdigit() and 0 <= int(b_str) <= 36:
                bk = b_str
            else:
                parse_error = f"❌ `{b_str}` no es una apuesta válida."
                break
            if amt <= 0:
                parse_error = "❌ Todas las apuestas deben ser mayores a 0."
                break
            slots.append((amt, bk))
            i += 2

        if parse_error:
            await message.channel.send(f"{parse_error}\n{ROULETTE_HELP}")
            return
        if not slots:
            await message.channel.send(ROULETTE_HELP)
            return

        total_cost = sum(a for a, _ in slots)
        if bal < total_cost:
            embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
            embed.description = (
                f"El total de tus apuestas es **{total_cost:,}** 🪙\n"
                f"Tienes **{bal:,}** 🪙."
            )
            await message.channel.send(embed=embed)
            return

        resultado = random.randint(0, 36)
        embed, net = _build_multibets_embed(resultado, slots, bal)
        await update_balance(user_id, net)
        await track_mission(user_id, "roulette_played")
        await log_bet(user_id, "🎰 Ruleta", sum(a for a, _ in slots), net)
        await message.channel.send(embed=embed)

    # ,bj <cantidad|all>
    elif cmd == "bj":
        await get_or_create_user(user_id, message.author.name)
        bal = await get_balance(user_id)

        if not args:
            await message.channel.send("❌ Uso: `,bj <cantidad|all>`\nEjemplo: `,bj all` o `,bj 5000`")
            return

        amount_str = args[0].lower()
        if amount_str == "all":
            cantidad = bal
        else:
            try:
                cantidad = int(amount_str)
            except ValueError:
                await message.channel.send("❌ Uso: `,bj <cantidad|all>`")
                return

        if cantidad <= 0:
            await message.channel.send("❌ La apuesta debe ser mayor a 0.")
            return
        if bal < cantidad:
            embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
            embed.description = f"Tienes **{bal:,}** 🪙 y quieres apostar **{cantidad:,}** 🪙."
            await message.channel.send(embed=embed)
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
            await message.channel.send(embed=embed)
            return

        view = BlackjackView(user_id, cantidad, player_hand, dealer_hand, deck, bal)
        embed = bj_embed(player_hand, dealer_hand, cantidad)
        await message.channel.send(embed=embed, view=view)

    # ,dep <cantidad|all>
    elif cmd == "dep":
        await get_or_create_user(user_id, message.author.name)
        wallet = await get_balance(user_id)

        if not args:
            await message.channel.send("❌ Uso: `,dep <cantidad|all>`\nEjemplo: `,dep all` o `,dep 5000`")
            return

        amount_str = args[0].lower()
        if amount_str == "all":
            amount = wallet
        else:
            try:
                amount = int(amount_str)
            except ValueError:
                await message.channel.send("❌ Escribe un número o `all`. Ejemplo: `,dep all`")
                return

        if amount <= 0:
            await message.channel.send("❌ La cantidad debe ser mayor a 0.")
            return
        if amount > wallet:
            embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
            embed.description = f"Solo tienes **{wallet:,}** 🪙 en cartera."
            await message.channel.send(embed=embed)
            return

        await update_balance(user_id, -amount)
        await update_bank(user_id, amount)
        new_wallet = await get_balance(user_id)
        new_bank = await get_bank(user_id)

        embed = discord.Embed(title="🏦 Depósito Exitoso", color=0x3498DB)
        embed.description = f"Depositaste **{amount:,}** 🪙 en el banco.\n"
        embed.add_field(name="👛 Cartera", value=f"**{new_wallet:,}** 🪙", inline=True)
        embed.add_field(name="🏦 Banco", value=f"**{new_bank:,}** 🪙", inline=True)
        embed.set_footer(text="El banco está protegido contra robos")
        await message.channel.send(embed=embed)

    # ,withdraw <cantidad|all>
    elif cmd == "withdraw":
        await get_or_create_user(user_id, message.author.name)
        bank_bal = await get_bank(user_id)

        if not args:
            await message.channel.send("❌ Uso: `,withdraw <cantidad|all>`\nEjemplo: `,withdraw all` o `,withdraw 5000`")
            return

        amount_str = args[0].lower()
        if amount_str == "all":
            amount = bank_bal
        else:
            try:
                amount = int(amount_str)
            except ValueError:
                await message.channel.send("❌ Escribe un número o `all`. Ejemplo: `,withdraw all`")
                return

        if amount <= 0:
            await message.channel.send("❌ La cantidad debe ser mayor a 0.")
            return
        if amount > bank_bal:
            embed = discord.Embed(title="❌ Saldo Bancario Insuficiente", color=0xFF4444)
            embed.description = f"Solo tienes **{bank_bal:,}** 🪙 en el banco."
            await message.channel.send(embed=embed)
            return

        await update_bank(user_id, -amount)
        await update_balance(user_id, amount)
        new_wallet = await get_balance(user_id)
        new_bank = await get_bank(user_id)

        embed = discord.Embed(title="🏦 Retiro Exitoso", color=0x00FF88)
        embed.description = f"Retiraste **{amount:,}** 🪙 del banco a tu cartera.\n"
        embed.add_field(name="👛 Cartera", value=f"**{new_wallet:,}** 🪙", inline=True)
        embed.add_field(name="🏦 Banco", value=f"**{new_bank:,}** 🪙", inline=True)
        await message.channel.send(embed=embed)

    # ,pay @usuario <cantidad|all>
    elif cmd == "pay":
        await get_or_create_user(user_id, message.author.name)

        # Necesitamos al menos 2 args: @usuario y cantidad
        if len(args) < 2:
            await message.channel.send("❌ Uso: `,pay @usuario <cantidad|all>`\nEjemplo: `,pay @Alguien all` o `,pay @Alguien 5000`")
            return

        # Resolver el usuario mencionado
        target_member = None
        if message.mentions:
            target_member = message.mentions[0]
        else:
            await message.channel.send("❌ Menciona al usuario. Ejemplo: `,pay @Alguien 5000`")
            return

        if target_member.id == message.author.id:
            await message.channel.send("❌ No puedes transferirte dinero a ti mismo.")
            return
        if target_member.bot:
            await message.channel.send("❌ No puedes enviarle monedas a un bot.")
            return

        sender_balance = await get_balance(user_id)
        # La cantidad es el último argumento (puede ser "all" o número)
        amount_str = args[-1].lower()
        if amount_str == "all":
            cantidad = sender_balance
        else:
            try:
                cantidad = int(amount_str)
            except ValueError:
                await message.channel.send("❌ Escribe un número o `all`. Ejemplo: `,pay @Alguien all`")
                return

        if cantidad <= 0:
            await message.channel.send("❌ La cantidad debe ser mayor a 0.")
            return
        if sender_balance < cantidad:
            embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
            embed.description = f"Tienes **{sender_balance:,}** 🪙 y quieres enviar **{cantidad:,}** 🪙."
            await message.channel.send(embed=embed)
            return

        receiver_id = str(target_member.id)
        await get_or_create_user(receiver_id, target_member.name)
        await update_balance(user_id, -cantidad)
        await update_balance(receiver_id, cantidad)

        embed = discord.Embed(title="💸 Transferencia Exitosa", color=0x00FF88)
        embed.description = (
            f"**{message.author.mention}** le envió **{cantidad:,}** 🪙 a **{target_member.mention}**.\n\n"
            f"👛 Tu nuevo saldo: **{sender_balance - cantidad:,}** 🪙"
        )
        await message.channel.send(embed=embed)

    # ,work / ,slut / ,crime — los valores se configuran desde el panel web
    elif cmd in ("work", "slut", "crime"):
        await message.channel.send(embed=await run_income_command(cmd, user_id, message.author.name))

    # ,rob @usuario
    elif cmd == "rob":
        await get_or_create_user(user_id, message.author.name)

        if not message.mentions:
            await message.channel.send("❌ Menciona al usuario. Ejemplo: `,rob @Alguien`")
            return

        target = message.mentions[0]
        if target.id == message.author.id:
            await message.channel.send("❌ No puedes robarte a ti mismo.")
            return
        if target.bot:
            await message.channel.send("❌ No puedes robarle a un bot.")
            return

        victim_id = str(target.id)
        await get_or_create_user(victim_id, target.name)

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT last_rob FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                last_rob = row[0] if row else None

        now = datetime.utcnow()
        if last_rob:
            diff = now - datetime.fromisoformat(last_rob)
            if diff < timedelta(minutes=ROB_COOLDOWN_MINUTES):
                remaining = timedelta(minutes=ROB_COOLDOWN_MINUTES) - diff
                mins = int(remaining.total_seconds() // 60)
                secs = int(remaining.total_seconds() % 60)
                embed = discord.Embed(title="⏰ Cooldown Activo", color=0xFF4444)
                embed.description = f"Espera **{mins}m {secs}s** antes de volver a intentarlo."
                await message.channel.send(embed=embed)
                return

        victim_balance = await get_balance(victim_id)
        if victim_balance < 100:
            embed = discord.Embed(title="😅 Víctima Sin Fondos", color=0xFFAA00)
            embed.description = f"**{target.name}** tiene menos de 100 🪙. ¡No vale la pena!"
            await message.channel.send(embed=embed)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET last_rob = ? WHERE user_id = ?", (now.isoformat(), user_id))
            await db.commit()

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT shield_until FROM users WHERE user_id = ?", (victim_id,)) as cur:
                srow = await cur.fetchone()
                shield_until = srow[0] if srow else None
        if shield_until:
            shield_dt = datetime.fromisoformat(shield_until)
            if datetime.utcnow() < shield_dt:
                remaining_shield = shield_dt - datetime.utcnow()
                mins_s = int(remaining_shield.total_seconds() // 60)
                embed = discord.Embed(title="🛡️ ¡Robo Bloqueado!", color=0x3498DB)
                embed.description = (
                    f"**{target.mention}** tiene un **Escudo Anti-Robos** activo.\n"
                    f"⏰ Su escudo dura **{mins_s} min** más. ¡No puedes robarle ahora!"
                )
                await message.channel.send(embed=embed)
                return

        success = random.random() < ROB_SUCCESS_CHANCE / 100
        if success:
            pct = random.uniform(ROB_STEAL_MIN_PCT / 100, ROB_STEAL_MAX_PCT / 100)
            stolen = max(1, int(victim_balance * pct))
            stolen = min(stolen, victim_balance)
            await update_balance(victim_id, -stolen)
            await update_balance(user_id, stolen)
            await track_mission(user_id, "rob_success")
            robber_balance = await get_balance(user_id)
            embed = discord.Embed(title="🦹 ¡Robo Exitoso!", color=0x00FF88)
            embed.description = (
                f"¡Le robaste **{stolen:,}** 🪙 a **{target.mention}**!\n\n"
                f"Tu saldo: **{robber_balance:,}** 🪙"
            )
        else:
            fine = max(1, int(victim_balance * ROB_FINE_PCT / 100))
            robber_balance = await get_balance(user_id)
            fine = min(fine, robber_balance)
            await update_balance(user_id, -fine)
            jail_minutes = await jail_send(user_id)
            embed = discord.Embed(title="🚔 ¡Te Atraparon!", color=0xFF4444)
            embed.description = (
                f"Intentaste robar a **{target.mention}** pero te atraparon.\n"
                f"Multa: **{fine:,}** 🪙\n\n"
                f"Tu saldo: **{robber_balance - fine:,}** 🪙\n\n"
                f"🔒 **Vas a la cárcel {jail_minutes} min.** No podrás robar ni apostar. Sal antes con `,fianza`."
            )
        await message.channel.send(embed=embed)

    # ,daily — recompensa diaria con racha (cooldown 24h)
    elif cmd == "daily":
        row = await get_or_create_user(user_id, message.author.name)
        last_daily = row[1]
        now = datetime.utcnow()

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT daily_streak FROM users WHERE user_id = ?", (user_id,)) as cur:
                srow = await cur.fetchone()
                current_streak = (srow[0] or 0) if srow else 0

        if last_daily:
            last_dt = datetime.fromisoformat(last_daily)
            diff = now - last_dt
            if diff < timedelta(hours=24):
                remaining = timedelta(hours=24) - diff
                hours_r, rem = divmod(int(remaining.total_seconds()), 3600)
                mins_r = rem // 60
                embed = discord.Embed(title="⏰ Recompensa No Disponible", color=0xFF4444)
                embed.description = f"Ya recogiste tu recompensa diaria.\nVuelve en **{hours_r}h {mins_r}m**."
                await message.channel.send(embed=embed)
                return
            new_streak = (current_streak + 1) if diff < timedelta(hours=48) else 1
        else:
            new_streak = 1

        if new_streak > 30:
            new_streak = 1

        reward = calc_daily_reward(new_streak)
        next_reward = calc_daily_reward(min(new_streak + 1, 30))

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET balance = balance + ?, last_daily = ?, daily_streak = ? WHERE user_id = ?",
                (reward, now.isoformat(), new_streak, user_id)
            )
            await db.commit()

        bal = await get_balance(user_id)
        streak_bar = "🔥" * min(new_streak, 10) + ("+" if new_streak > 10 else "")
        embed = discord.Embed(title="🎁 ¡Recompensa Diaria!", color=0x00FF88)
        embed.description = (
            f"{streak_bar}\n"
            f"**Día {new_streak}** de racha\n\n"
            f"💰 Recibiste: **{reward:,}** 🪙\n"
            f"📅 Mañana (día {min(new_streak+1,30)}): **{next_reward:,}** 🪙\n\n"
            f"👛 Saldo actual: **{bal:,}** 🪙"
        )
        await track_mission(user_id, "daily_used")
        await message.channel.send(embed=embed)

    # ,duel @usuario <cantidad>
    elif cmd == "duel":
        await get_or_create_user(user_id, message.author.name)

        if not message.mentions or len(args) < 2:
            await message.channel.send("❌ Uso: `,duel @usuario <cantidad>`\nEjemplo: `,duel @Alguien 5000`")
            return

        target = message.mentions[0]
        if target.id == message.author.id:
            await message.channel.send("❌ No puedes retarte a ti mismo.")
            return
        if target.bot:
            await message.channel.send("❌ No puedes retar a un bot.")
            return

        try:
            cantidad = int(args[-1])
        except ValueError:
            await message.channel.send("❌ Escribe una cantidad válida. Ejemplo: `,duel @Alguien 5000`")
            return

        if cantidad <= 0:
            await message.channel.send("❌ La apuesta debe ser mayor a 0.")
            return

        challenger_balance = await get_balance(user_id)
        if challenger_balance < cantidad:
            embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
            embed.description = f"Necesitas **{cantidad:,}** 🪙 y tienes **{challenger_balance:,}** 🪙."
            await message.channel.send(embed=embed)
            return

        await get_or_create_user(str(target.id), target.name)

        embed = discord.Embed(title="⚔️ ¡Duelo de Dados!", color=0xE74C3C)
        embed.description = (
            f"**{message.author.mention}** reta a **{target.mention}** a un duelo de dados.\n\n"
            f"🎲 Cada jugador lanzará un dado del 1 al 6\n"
            f"🏆 El mayor número gana todo\n"
            f"🤝 Si empatan, se devuelve la apuesta\n\n"
            f"💰 Apuesta: **{cantidad:,}** 🪙 cada uno\n"
            f"🏆 Premio total: **{cantidad*2:,}** 🪙\n\n"
            f"{target.mention}, tienes **60 segundos** para aceptar o rechazar."
        )
        view = DuelChallengeView(
            challenger_id=user_id,
            challenger_name=message.author.name,
            challenged=target,
            bet=cantidad,
        )
        await message.channel.send(embed=embed, view=view)

    # ,torneo <entrada>
    elif cmd == "torneo":
        await get_or_create_user(user_id, message.author.name)

        if not args:
            await message.channel.send("❌ Uso: `,torneo <entrada>`\nEjemplo: `,torneo 5000`")
            return

        try:
            entrada = int(args[0])
        except ValueError:
            await message.channel.send("❌ Escribe una cantidad válida. Ejemplo: `,torneo 5000`")
            return

        if entrada <= 0:
            await message.channel.send("❌ El costo de entrada debe ser mayor a 0.")
            return

        bal = await get_balance(user_id)
        if bal < entrada:
            await message.channel.send(f"❌ Necesitas **{entrada:,}** 🪙 para crear el torneo. Tienes **{bal:,}** 🪙.")
            return

        await update_balance(user_id, -entrada)
        view = TournamentView(host_id=user_id, host_name=message.author.display_name, buy_in=entrada)
        view.players.append((user_id, message.author.display_name))

        sent = await message.channel.send(embed=view.make_embed(), view=view)
        view.message = sent

    # ,addmoney <@usuario> <cantidad> — solo administradores
    elif cmd == "addmoney":
        if not message.author.guild_permissions.administrator:
            await message.channel.send("❌ Solo los administradores pueden usar este comando.")
            return
        if len(args) < 2:
            await message.channel.send("❌ Uso: `,addmoney <@usuario> <cantidad>`")
            return
        target = message.mentions[0] if message.mentions else None
        if not target:
            await message.channel.send("❌ Debes mencionar a un usuario. Ej: `,addmoney @usuario 50000`")
            return
        try:
            amount = int(args[1].replace(",", "").replace(".", ""))
        except ValueError:
            await message.channel.send("❌ La cantidad debe ser un número entero.")
            return
        if amount <= 0:
            await message.channel.send("❌ La cantidad debe ser mayor a 0.")
            return
        await get_or_create_user(str(target.id), target.name)
        await update_balance(str(target.id), amount)
        new_bal = await get_balance(str(target.id))
        embed = discord.Embed(title="💰 Dinero Añadido", color=0x00FF88)
        embed.description = (
            f"✅ Se añadieron **{amount:,}** 🪙 a {target.mention}\n"
            f"📊 Nuevo saldo: **{new_bal:,}** 🪙\n\n"
            f"_Por: {message.author.display_name}_"
        )
        await message.channel.send(embed=embed)

    # ,removemoney <@usuario> <cantidad> — solo administradores
    elif cmd == "removemoney":
        if not message.author.guild_permissions.administrator:
            await message.channel.send("❌ Solo los administradores pueden usar este comando.")
            return
        target = message.mentions[0] if message.mentions else None
        amount_args = [a for a in args if not re.fullmatch(r"<@!?\d+>", a)]
        if not target or not amount_args:
            await message.channel.send("❌ Uso: `,removemoney @usuario <cantidad|all> [banco]` — ej: `,removemoney @Juan all`")
            return
        include_bank = any(a.lower() in ("banco", "bank") for a in amount_args[1:])
        result = await perform_removemoney(target, amount_args[0], include_bank)
        if isinstance(result, str):
            await message.channel.send(result)
        else:
            result.set_footer(text=f"Por: {message.author.display_name}")
            await message.channel.send(embed=result)

    # ,fighters — lista luchadores disponibles
    elif cmd == "fighters":
        embed = discord.Embed(title="🥊 Luchadores del Casino", color=0xFF6B00)
        embed.description = "Compra con `,buyfighter <id>` y pelea con `,fight @usuario`.\n\u200b"
        for fid, f in FIGHTERS.items():
            embed.add_field(
                name=f"{f['name']} — `{fid}`",
                value=f"💰 {f['price']:,} 🪙\n❤️ HP: {f['hp']} | ⚔️ ATK: {f['attack']} | 🛡️ DEF: {f['defense']}\n_{f['description']}_",
                inline=False
            )
        await message.channel.send(embed=embed)

    # ,buyfighter <id>
    elif cmd == "buyfighter":
        await get_or_create_user(user_id, message.author.name)
        fid = resolve_fighter(" ".join(args)) if args else None
        if fid is None:
            note = f"❌ No encontré **{' '.join(args)}**. Elige uno en el panel:" if args else None
            await message.channel.send(
                note, embed=build_fighter_shop_embed(), view=FighterShopView(message.author.id)
            )
            return
        f = FIGHTERS[fid]
        bal = await get_balance(user_id)
        if bal < f["price"]:
            await message.channel.send(f"❌ Te faltan **{f['price'] - bal:,}** 🪙 para comprar **{f['name']}**.")
            return
        await update_balance(user_id, -f["price"])
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO fighters (user_id, fighter_id) VALUES (?, ?)", (user_id, fid))
            await db.commit()
        embed = discord.Embed(title="🥊 ¡Luchador Comprado!", color=0x00FF88)
        embed.description = (
            f"Ahora tienes a **{f['name']}** en tu equipo.\n\n"
            f"❤️ HP: {f['hp']} | ⚔️ ATK: {f['attack']} | 🛡️ DEF: {f['defense']}\n\n"
            f"_Reta a alguien con `,fight @usuario`_"
        )
        await message.channel.send(embed=embed)

    # ,myfighter
    elif cmd == "myfighter":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT fighter_id FROM fighters WHERE user_id = ?", (user_id,)) as cur:
                row = await cur.fetchone()
        if not row:
            await message.channel.send("❌ No tienes luchador. Compra uno con `,buyfighter`.")
            return
        fid = row[0]
        s = await get_fighter_stats(user_id, fid)
        base = FIGHTERS[fid]
        xp_needed = s["level"] * 20
        bar_filled = int((s["xp"] / xp_needed) * 10) if xp_needed > 0 else 0
        xp_bar = "█" * bar_filled + "░" * (10 - bar_filled)
        embed = discord.Embed(title=f"🥊 {s['name']} — Nivel {s['level']}", color=0xFF6B00)
        embed.description = (
            f"**Stats actuales:**\n"
            f"❤️ HP: **{s['hp']}** (+{s['bonus_hp']})\n"
            f"⚔️ ATK: **{s['attack']}** (+{s['bonus_attack']})\n"
            f"🛡️ DEF: **{s['defense']}** (+{s['bonus_defense']})\n\n"
            f"📊 XP: `{xp_bar}` {s['xp']}/{xp_needed}\n"
            f"🎯 Puntos disponibles: **{s['points']}**\n\n"
            f"_{base['description']}_\n\n"
            f"Usa `,addpuntos <stat> <cantidad>` para mejorar tu luchador.\n"
            f"Stats: `ataque`, `defensa`, `salud`"
        )
        await message.channel.send(embed=embed)

    # ,fight @usuario
    elif cmd == "fight":
        await get_or_create_user(user_id, message.author.name)
        if not message.mentions:
            await message.channel.send("❌ Menciona al usuario. Ejemplo: `,fight @Alguien`")
            return
        target = message.mentions[0]
        if target.id == message.author.id:
            await message.channel.send("❌ No puedes pelearte contigo mismo.")
            return
        if target.bot:
            await message.channel.send("❌ No puedes retar a un bot.")
            return
        uid2 = str(target.id)
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT last_fight FROM fight_cooldowns WHERE user_id = ?", (user_id,)) as cur:
                crow = await cur.fetchone()
        if crow and crow[0]:
            diff = datetime.utcnow() - datetime.fromisoformat(crow[0])
            if diff < timedelta(seconds=30):
                rem = timedelta(seconds=30) - diff
                s = int(rem.total_seconds())
                await message.channel.send(f"⏰ Espera **{s}s** antes de volver a pelear.")
                return
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT fighter_id FROM fighters WHERE user_id = ?", (user_id,)) as cur:
                r1 = await cur.fetchone()
            async with db.execute("SELECT fighter_id FROM fighters WHERE user_id = ?", (uid2,)) as cur:
                r2 = await cur.fetchone()
        if not r1:
            await message.channel.send("❌ No tienes luchador. Compra uno con `,buyfighter`.")
            return
        if not r2:
            await message.channel.send(f"❌ **{target.name}** no tiene luchador.")
            return
        s1 = await get_fighter_stats(user_id, r1[0])
        s2 = await get_fighter_stats(uid2, r2[0])
        win_idx, battle_log = simulate_fight_stats(s1, s2)
        winner_id  = user_id if win_idx == 0 else uid2
        loser_id   = uid2 if win_idx == 0 else user_id
        winner_fid = r1[0] if win_idx == 0 else r2[0]
        loser_fid  = r2[0] if win_idx == 0 else r1[0]
        winner_mem = message.author if winner_id == user_id else target
        loser_mem  = target if winner_id == user_id else message.author
        loser_bal = await get_balance(loser_id)
        prize = max(1, int(loser_bal * 0.10))
        await update_balance(loser_id, -prize)
        await update_balance(winner_id, prize)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO fight_cooldowns (user_id, last_fight) VALUES (?, ?)",
                             (user_id, datetime.utcnow().isoformat()))
            await db.commit()
        new_lvl, _, pts_gained = await add_fighter_xp(winner_id, winner_fid, 15)
        await add_fighter_xp(loser_id, loser_fid, 5)
        level_up_msg = f"\n🆙 **¡{winner_mem.display_name} subió al nivel {new_lvl}!** +{pts_gained} puntos" if pts_gained else ""
        embed = discord.Embed(title="🥊 ¡COMBATE!", color=0xFF0000)
        embed.description = (
            f"**{message.author.display_name}** ({s1['name']} Nv.{s1['level']}) vs "
            f"**{target.display_name}** ({s2['name']} Nv.{s2['level']})\n\n"
            f"{battle_log}\n\n"
            f"🏆 **¡{winner_mem.mention} gana!**\n"
            f"💰 Premio: **{prize:,}** 🪙 de {loser_mem.mention}"
            f"{level_up_msg}"
        )
        await message.channel.send(embed=embed)

    # ,addlevel @usuario <fighter_id> <niveles> — solo admins
    elif cmd == "addlevel":
        if not message.author.guild_permissions.administrator:
            await message.channel.send("❌ Solo los administradores pueden usar este comando.")
            return
        target = message.mentions[0] if message.mentions else message.author
        target_id = str(target.id)
        remaining_args = [a for a in args if not a.startswith("<@")]
        if len(remaining_args) < 2:
            await message.channel.send("❌ Uso: `,addlevel @usuario <fighter_id> <niveles>`\nEj: `,addlevel @Juan novato 50`")
            return
        fid = remaining_args[0].lower()
        if fid not in FIGHTERS:
            ids = ", ".join(f"`{k}`" for k in FIGHTERS)
            await message.channel.send(f"❌ ID de luchador inválido. IDs válidos: {ids}")
            return
        try:
            add_lvls = int(remaining_args[1])
        except ValueError:
            await message.channel.send("❌ Los niveles deben ser un número entero.")
            return
        if add_lvls <= 0:
            await message.channel.send("❌ Debes agregar al menos 1 nivel.")
            return
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT fighter_id FROM fighters WHERE user_id=?", (target_id,)) as cur:
                frow = await cur.fetchone()
        if not frow:
            await message.channel.send(f"❌ **{target.name}** no tiene ningún luchador comprado.")
            return
        if frow[0] != fid:
            await message.channel.send(f"❌ **{target.name}** tiene un **{FIGHTERS[frow[0]]['name']}**, no un **{FIGHTERS[fid]['name']}**.")
            return
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT level, xp, points FROM fighter_levels WHERE user_id=? AND fighter_id=?",
                (target_id, fid)
            ) as cur:
                lvl_row = await cur.fetchone()
        cur_level, cur_xp, cur_points = lvl_row if lvl_row else (1, 0, 0)
        new_level = cur_level + add_lvls
        points_gained = add_lvls * 5
        new_points = cur_points + points_gained
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO fighter_levels (user_id, fighter_id, level, xp, points) VALUES (?,?,?,?,?) "
                "ON CONFLICT(user_id, fighter_id) DO UPDATE SET level=excluded.level, xp=excluded.xp, points=excluded.points",
                (target_id, fid, new_level, 0, new_points)
            )
            await db.commit()
        f = FIGHTERS[fid]
        embed = discord.Embed(title="🆙 ¡Niveles Añadidos!", color=0x00FF88)
        embed.description = (
            f"Se añadieron **{add_lvls}** niveles al luchador **{f['name']}** de {target.mention}\n\n"
            f"📊 Nivel anterior: **{cur_level}** → Nivel nuevo: **{new_level}**\n"
            f"🎯 Puntos ganados: **+{points_gained}** (total disponible: **{new_points}**)\n\n"
            f"_Por: {message.author.display_name}_"
        )
        await message.channel.send(embed=embed)

    # ,addpuntos [stat] [cantidad]
    elif cmd == "addpuntos":
        await get_or_create_user(user_id, message.author.name)
        embed, error, st = await points_panel_embed(user_id)
        if error:
            await message.channel.send(error.replace("/buyfighter", ",buyfighter"))
            return
        key = resolve_stat(args[0]) if args else None
        if key is None:
            note = f"❌ No encontré la estadística **{args[0]}**. Elige una en el panel:" if args else None
            await message.channel.send(note, embed=embed, view=StatPanelView(user_id))
            return
        if len(args) < 2:
            if st["points"] <= 0:
                await message.channel.send("❌ No tienes puntos disponibles.")
                return
            await message.channel.send(
                embed=stat_quantity_embed(key, st["points"]),
                view=StatQuantityView(user_id, key, st["points"]),
            )
            return
        try:
            cantidad = int(args[1])
        except ValueError:
            await message.channel.send("❌ La cantidad debe ser un número entero.")
            return
        if cantidad <= 0:
            await message.channel.send("❌ La cantidad debe ser mayor a 0.")
            return
        result, error, _left = await apply_stat_points(user_id, key, cantidad)
        if error:
            await message.channel.send(error)
            return
        await message.channel.send(embed=result)

    # ,ftorneo — torneo de luchadores
    elif cmd == "ftorneo":
        await get_or_create_user(user_id, message.author.name)
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT fighter_id FROM fighters WHERE user_id = ?", (user_id,)) as cur:
                row = await cur.fetchone()
        if not row:
            await message.channel.send("❌ Necesitas un luchador para organizar un torneo. Compra uno con `,buyfighter`.")
            return
        entry_fee = loan_parse_amount(args[0]) if args else 0
        if entry_fee is None or entry_fee < 0:
            await message.channel.send("❌ Uso: `,ftorneo [apuesta de entrada]` — ej: `,ftorneo 5m`")
            return
        charge_error = await ftorneo_charge_host(user_id, entry_fee)
        if charge_error:
            await message.channel.send(charge_error)
            return
        view = FighterTournamentView(host_id=user_id, host_name=message.author.display_name, entry_fee=entry_fee)
        view.players.append((user_id, message.author.display_name, row[0]))
        sent = await message.channel.send(embed=view.make_embed(), view=view)
        view.message = sent

    # ,reset-money [@usuario] — todos en sí mismos, admins en cualquiera
    elif cmd in ("reset-money", "resetmoney", "resetbal"):
        is_admin = message.author.guild_permissions.administrator
        target = message.mentions[0] if message.mentions else None
        if target and not is_admin:
            await message.channel.send("❌ Solo los administradores pueden resetear el saldo de otros usuarios.")
            return
        if not target:
            target = message.author
        target_id = str(target.id)
        await get_or_create_user(target_id, target.name)
        cur_bal = await get_balance(target_id)
        await update_balance(target_id, -cur_bal)
        embed = discord.Embed(title="🔄 Saldo Reseteado", color=0xFF8800)
        if target.id == message.author.id:
            embed.description = f"Tu saldo de cartera ha sido reseteado a **0** 🪙."
        else:
            embed.description = (
                f"El saldo de {target.mention} ha sido reseteado a **0** 🪙.\n"
                f"_(Tenía **{cur_bal:,}** 🪙)_\n\n"
                f"_Por: {message.author.display_name}_"
            )
        await message.channel.send(embed=embed)

    # ,lottery [cantidad|info]
    elif cmd in ("lottery", "loto", "loteria", "lotería"):
        await get_or_create_user(user_id, message.author.name)

        sub = args[0].lower() if args else ""

        # ,lottery info — ver estado del bote
        if sub == "info":
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT SUM(tickets), COUNT(*) FROM lottery_tickets WHERE tickets > 0") as cur:
                    row = await cur.fetchone()
                    total_tickets = row[0] or 0
                    total_players = row[1] or 0
                async with db.execute("SELECT tickets FROM lottery_tickets WHERE user_id = ?", (user_id,)) as cur:
                    trow = await cur.fetchone()
                    my_tickets = (trow[0] or 0) if trow else 0
                async with db.execute("SELECT value FROM lottery_meta WHERE key = 'last_draw'") as cur:
                    mrow = await cur.fetchone()
                    last_draw = mrow[0] if mrow else None

            pot = total_tickets * LOTTERY_TICKET_PRICE
            if last_draw:
                next_draw_dt = datetime.fromisoformat(last_draw) + timedelta(days=7)
                remaining = next_draw_dt - datetime.utcnow()
                if remaining.total_seconds() > 0:
                    days_r = remaining.days
                    hours_r = remaining.seconds // 3600
                    mins_r = (remaining.seconds % 3600) // 60
                    time_str = f"**{days_r}d {hours_r}h {mins_r}m**"
                else:
                    time_str = "**¡Muy pronto!**"
            else:
                time_str = "**7 días desde el primer boleto**"

            embed = discord.Embed(title="🎰 Lotería del Casino", color=0xFFD700)
            embed.description = (
                f"💰 **Bote actual:** {pot:,} 🪙\n"
                f"🎟️ **Boletos vendidos:** {total_tickets:,}\n"
                f"👥 **Participantes:** {total_players}\n"
                f"⏰ **Próximo sorteo en:** {time_str}\n\n"
                f"🎫 **Tus boletos:** {my_tickets}\n\n"
                f"Cada boleto cuesta **{LOTTERY_TICKET_PRICE:,}** 🪙\n"
                f"Usa `,lottery <cantidad>` para comprar boletos.\n"
                f"Más boletos = más probabilidad de ganar 🍀"
            )
            await message.channel.send(embed=embed)
            return

        # ,lottery [n] — comprar boletos
        if sub == "" or sub.isdigit():
            cantidad = int(sub) if sub.isdigit() else 1
        else:
            await message.channel.send(
                "❌ Uso: `,lottery [cantidad]` para comprar boletos o `,lottery info` para ver el bote."
            )
            return

        if cantidad < 1:
            await message.channel.send("❌ Debes comprar al menos 1 boleto.")
            return
        if cantidad > 100:
            await message.channel.send("❌ Máximo 100 boletos por compra.")
            return

        total_cost = cantidad * LOTTERY_TICKET_PRICE
        bal = await get_balance(user_id)
        if bal < total_cost:
            embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
            embed.description = (
                f"Comprar **{cantidad}** boleto(s) cuesta **{total_cost:,}** 🪙.\n"
                f"Tienes **{bal:,}** 🪙 en cartera."
            )
            await message.channel.send(embed=embed)
            return

        await update_balance(user_id, -total_cost)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO lottery_tickets (user_id, username, tickets) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET tickets = tickets + ?, username = ?",
                (user_id, message.author.name, cantidad, cantidad, message.author.name)
            )
            await db.execute(
                "INSERT OR REPLACE INTO lottery_channels (guild_id, channel_id) VALUES (?, ?)",
                (str(message.guild.id) if message.guild else "0", str(message.channel.id))
            )
            await db.commit()

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT tickets FROM lottery_tickets WHERE user_id = ?", (user_id,)) as cur:
                trow = await cur.fetchone()
                my_total = trow[0] if trow else cantidad
            async with db.execute("SELECT SUM(tickets) FROM lottery_tickets WHERE tickets > 0") as cur:
                srow = await cur.fetchone()
                total_tickets = srow[0] or 0

        pot = total_tickets * LOTTERY_TICKET_PRICE
        new_bal = await get_balance(user_id)

        embed = discord.Embed(title="🎟️ ¡Boleto(s) Comprado(s)!", color=0x00FF88)
        embed.description = (
            f"Compraste **{cantidad}** boleto(s) por **{total_cost:,}** 🪙\n\n"
            f"🎫 Tus boletos totales: **{my_total}**\n"
            f"💰 Bote actual: **{pot:,}** 🪙\n"
            f"🎟️ Boletos totales: **{total_tickets}**\n\n"
            f"👛 Saldo restante: **{new_bal:,}** 🪙\n\n"
            f"_El sorteo es automático cada **7 días**. ¡Buena suerte! 🍀_"
        )
        await message.channel.send(embed=embed)

    # ,slots <cantidad|all>
    elif cmd in ("slots", "slot", "tragamonedas"):
        await get_or_create_user(user_id, message.author.name)
        bal = await get_balance(user_id)
        if not args:
            await message.channel.send("❌ Uso: `,slots <cantidad|all>`")
            return
        if args[0].lower() == "all":
            cantidad = bal
        else:
            try:
                cantidad = int(args[0])
            except ValueError:
                await message.channel.send("❌ Uso: `,slots <cantidad|all>`")
                return
        if cantidad <= 0:
            await message.channel.send("❌ La apuesta debe ser mayor a 0.")
            return
        if bal < cantidad:
            embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
            embed.description = f"Tienes **{bal:,}** 🪙 y quieres apostar **{cantidad:,}** 🪙."
            await message.channel.send(embed=embed)
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
            title = "🎰 ¡¡¡JACKPOT!!!" if symbol == "7️⃣" else ("🎰 ¡GRAN PREMIO!" if symbol == "💎" else "🎰 ¡GANASTE!")
            color = 0xFFD700 if symbol == "7️⃣" else (0x00FFFF if symbol == "💎" else 0x00FF88)
            embed = discord.Embed(title=title, color=color)
            embed.description = (
                f"╔══════════════╗\n║  {display}  ║\n╚══════════════╝\n\n"
                f"¡Tres **{symbol}**! Multiplicador **x{multiplier}**\n"
                f"💰 Ganaste **{winnings:,}** 🪙\nSaldo: **{new_balance:,}** 🪙"
            )
        elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
            winnings = int(cantidad * 0.5)
            await update_balance(user_id, winnings)
            new_balance = await get_balance(user_id)
            embed = discord.Embed(title="🎰 ¡Par!", color=0xFFAA00)
            embed.description = (
                f"╔══════════════╗\n║  {display}  ║\n╚══════════════╝\n\n"
                f"Dos iguales — recuperas la mitad.\n"
                f"💰 Recuperas **{winnings:,}** 🪙\nSaldo: **{new_balance:,}** 🪙"
            )
        else:
            new_balance = await get_balance(user_id)
            embed = discord.Embed(title="🎰 Sin suerte...", color=0xFF4444)
            embed.description = (
                f"╔══════════════╗\n║  {display}  ║\n╚══════════════╝\n\n"
                f"💸 Perdiste **{cantidad:,}** 🪙\nSaldo: **{new_balance:,}** 🪙"
            )
        await message.channel.send(embed=embed)

    # ,leaderboard / ,lb / ,top
    elif cmd in ("leaderboard", "lb", "top"):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10") as cursor:
                rows = await cursor.fetchall()
        if not rows:
            await message.channel.send("❌ No hay usuarios registrados aún.")
            return
        medals = ["🥇", "🥈", "🥉"]
        embed = discord.Embed(title="🏆 Ranking del Casino", color=0xFFD700)
        description = ""
        for i, (username, bal) in enumerate(rows):
            prefix_m = medals[i] if i < 3 else f"**#{i+1}**"
            description += f"{prefix_m} **{username}** — {bal:,} 🪙\n"
        embed.description = description
        embed.set_footer(text="Top 10 jugadores más ricos")
        await message.channel.send(embed=embed)

    # ,ranking
    elif cmd == "ranking":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id, username, balance FROM users ORDER BY balance DESC LIMIT 10") as cursor:
                rows = await cursor.fetchall()
        if not rows:
            await message.channel.send("❌ No hay usuarios registrados aún.")
            return
        medals = ["🥇", "🥈", "🥉"]
        embed = discord.Embed(title="🏆 Ranking del Casino", color=0xFFD700)
        description = ""
        for i, (_, username, bal) in enumerate(rows):
            prefix_m = medals[i] if i < 3 else f"**#{i+1}**"
            description += f"{prefix_m} **{username}** — {bal:,} 🪙\n"
        embed.description = description
        embed.set_footer(text="Top 10 jugadores más ricos")
        await message.channel.send(embed=embed)

    # ,missions / ,misiones
    elif cmd in ("missions", "misiones"):
        await get_or_create_user(user_id, message.author.name)
        data = await get_missions_data(user_id)
        embed = discord.Embed(title="📋 Misiones Diarias", color=0xE67E22)
        embed.description = "Completa misiones cada día para ganar monedas extra. ¡Se reinician a medianoche!\n"
        total_earned = sum(m["reward"] for m in data if m["completed"])
        total_available = sum(m["reward"] for m in data)
        for m in data:
            bar_filled = int((m["progress"] / m["goal"]) * 10)
            bar = "█" * bar_filled + "░" * (10 - bar_filled)
            status = "✅ **COMPLETADA**" if m["completed"] else f"`[{bar}]` {m['progress']}/{m['goal']}"
            embed.add_field(name=f"{m['name']} — +{m['reward']:,} 🪙", value=f"{m['description']}\n{status}", inline=False)
        embed.set_footer(text=f"Ganadas hoy: {total_earned:,} / {total_available:,} 🪙")
        await message.channel.send(embed=embed)

    # ,blackjack — alias de ,bj
    elif cmd == "blackjack":
        await get_or_create_user(user_id, message.author.name)
        bal = await get_balance(user_id)
        if not args:
            await message.channel.send("❌ Uso: `,blackjack <cantidad|all>`\nEjemplo: `,blackjack all` o `,blackjack 5000`")
            return
        if args[0].lower() == "all":
            cantidad = bal
        else:
            try:
                cantidad = int(args[0])
            except ValueError:
                await message.channel.send("❌ La cantidad debe ser un número.")
                return
        if cantidad <= 0:
            await message.channel.send("❌ La apuesta debe ser mayor a 0.")
            return
        if bal < cantidad:
            embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
            embed.description = f"Tienes **{bal:,}** 🪙 y quieres apostar **{cantidad:,}** 🪙."
            await message.channel.send(embed=embed)
            return
        await update_balance(user_id, -cantidad)
        deck = create_deck()
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]
        result_msg, color = check_blackjack_result(player_hand, dealer_hand, cantidad)
        if "¡GANASTE" in result_msg or "BLACKJACK" in result_msg:
            await track_mission(user_id, "blackjack_won")
        view = BlackjackView(user_id=user_id, bet=cantidad, deck=deck, player_hand=player_hand, dealer_hand=dealer_hand)
        embed = discord.Embed(title="🃏 Blackjack", color=color)
        embed.description = (
            f"**Tu mano:** {hand_to_str(player_hand)} = **{hand_value(player_hand)}**\n"
            f"**Dealer:** {hand_to_str([dealer_hand[0]])} + 🂠\n\n"
            f"{result_msg}"
        )
        sent = await message.channel.send(embed=embed, view=view)
        view.message = sent

    # ,coinflip @usuario <cantidad>
    elif cmd in ("coinflip", "cf"):
        if not message.mentions:
            await message.channel.send("❌ Uso: `,coinflip @usuario <cantidad>`")
            return
        usuario = message.mentions[0]
        if usuario.id == message.author.id:
            await message.channel.send("❌ No puedes retarte a ti mismo.")
            return
        if usuario.bot:
            await message.channel.send("❌ No puedes retar a un bot.")
            return
        remaining = [a for a in args if not a.startswith("<@")]
        if not remaining:
            await message.channel.send("❌ Uso: `,coinflip @usuario <cantidad>`")
            return
        try:
            cantidad = int(remaining[0])
        except ValueError:
            await message.channel.send("❌ La cantidad debe ser un número.")
            return
        if cantidad <= 0:
            await message.channel.send("❌ La apuesta debe ser mayor a 0.")
            return
        challenger_id = str(message.author.id)
        await get_or_create_user(challenger_id, message.author.name)
        await get_or_create_user(str(usuario.id), usuario.name)
        challenger_balance = await get_balance(challenger_id)
        if challenger_balance < cantidad:
            embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
            embed.description = f"Necesitas **{cantidad:,}** 🪙 y tienes **{challenger_balance:,}** 🪙."
            await message.channel.send(embed=embed)
            return
        embed = discord.Embed(title="🪙 ¡Reto de Cara o Cruz!", color=0x9B59B6)
        embed.description = (
            f"**{message.author.mention}** reta a **{usuario.mention}**\n\n"
            f"💰 Apuesta: **{cantidad:,}** 🪙 cada uno\n"
            f"🏆 Premio total: **{cantidad*2:,}** 🪙\n\n"
            f"🎩 {message.author.name} → **CARA**\n"
            f"🎮 {usuario.name} → **CRUZ**\n\n"
            f"{usuario.mention}, tienes **60 segundos** para aceptar o rechazar."
        )
        view = CoinflipChallengeView(
            challenger_id=challenger_id,
            challenger_name=message.author.name,
            challenged=usuario,
            bet=cantidad,
        )
        await message.channel.send(embed=embed, view=view)

    # ,crash <cantidad|all>
    elif cmd == "crash":
        await get_or_create_user(user_id, message.author.name)
        bal = await get_balance(user_id)
        if not args:
            await message.channel.send("❌ Uso: `,crash <cantidad|all>`")
            return
        if args[0].lower() == "all":
            cantidad = bal
        else:
            try:
                cantidad = int(args[0])
            except ValueError:
                await message.channel.send("❌ La cantidad debe ser un número.")
                return
        if cantidad <= 0:
            await message.channel.send("❌ La apuesta debe ser mayor a 0.")
            return
        if bal < cantidad:
            embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
            embed.description = f"Tienes **{bal:,}** 🪙 y quieres apostar **{cantidad:,}** 🪙."
            await message.channel.send(embed=embed)
            return
        await update_balance(user_id, -cantidad)
        crash_point = generate_crash_point()
        view = CrashView(user_id=user_id, bet=cantidad, crash_point=crash_point)
        embed = view.make_embed()
        sent = await message.channel.send(embed=embed, view=view)
        view.message = sent
        await track_mission(user_id, "crash_played")
        asyncio.create_task(view.run())

    # ,buy <item_id>
    elif cmd == "buy":
        await get_or_create_user(user_id, message.author.name)
        qty, name_text = parse_name_and_quantity(args)
        if not name_text:
            await message.channel.send(
                embed=build_shop_embed(panel=True), view=ShopBuyView(user_id)
            )
            return
        item = resolve_shop_item(name_text)
        if item is None:
            await message.channel.send(
                f"❌ No encontré **{name_text}**. Elige uno en el panel:",
                embed=build_shop_embed(panel=True),
                view=ShopBuyView(user_id),
            )
            return
        embed = await complete_shop_purchase(message.author, item, qty)
        await message.channel.send(embed=embed)

    # ,inventory / ,inv
    elif cmd in ("inventory", "inv", "inventario"):
        await get_or_create_user(user_id, message.author.name)
        items = await get_inventory(user_id)
        embed = discord.Embed(title=f"🎒 Inventario de {message.author.name}", color=0x3498DB)
        if not items:
            embed.description = "Tu inventario está vacío.\nUsa `,shop` para ver los objetos disponibles."
        else:
            for item_id, qty in items:
                item_data = SHOP_ITEMS.get(item_id, {"name": item_id, "description": "Objeto desconocido"})
                embed.add_field(name=f"{item_data['name']} x{qty}", value=item_data["description"], inline=False)
        await message.channel.send(embed=embed)

    # ,use <item_id>
    elif cmd == "use":
        await get_or_create_user(user_id, message.author.name)
        if not args:
            ids = ", ".join(f"`{k}`" for k in SHOP_ITEMS.keys())
            await message.channel.send(f"❌ Uso: `,use <item_id>`\nIDs: {ids}")
            return
        item = resolve_shop_item(" ".join(args)) or normalize_shop_item_id(args[0])
        if item not in SHOP_ITEMS:
            ids = ", ".join(f"`{k}`" for k in SHOP_ITEMS.keys())
            await message.channel.send(f"❌ Objeto no encontrado. IDs válidos:\n{ids}")
            return
        qty = await get_item_quantity(user_id, item)
        if qty == 0:
            embed = discord.Embed(title="❌ Sin Objeto", color=0xFF4444)
            embed.description = f"No tienes **{SHOP_ITEMS[item]['name']}** en tu inventario.\nCómpralo en `,shop`."
            await message.channel.send(embed=embed)
            return
        item_data = SHOP_ITEMS[item]
        if item_data["category"] == "rol":
            if message.guild is None or not isinstance(message.author, discord.Member):
                await message.channel.send(
                    "Debes usar este comando dentro del servidor donde quieres reclamar el rol."
                )
                return
            try:
                role, already_has_role, error = await grant_shop_role(
                    message.guild, message.author, item
                )
            except discord.Forbidden:
                error = "No tengo permiso para crear o asignar roles. Necesito **Gestionar roles**."
                role = None
                already_has_role = False
            except discord.HTTPException:
                error = "Discord no pudo crear o asignar el rol. Inténtalo de nuevo."
                role = None
                already_has_role = False
            except aiosqlite.Error:
                error = "No pude guardar el rol del servidor. El objeto sigue en tu inventario; inténtalo de nuevo."
                role = None
                already_has_role = False

            if error:
                await message.channel.send(error)
                return

            claim_message = (
                f"Ya tienes el rol **{role.name}**."
                if already_has_role
                else f"Reclamaste el rol **{role.name}**; ya está asignado a tu cuenta."
            )
            await message.channel.send(
                f"{claim_message}\nEl objeto permanece en tu inventario para `,collect`."
            )
        elif item_data["category"] == "decorativo":
            flavor = USE_FLAVOR.get(item, f"Usas **{item_data['name']}**.")
            embed = discord.Embed(title=f"✨ Usando {item_data['name']}", color=0x9B59B6)
            embed.description = flavor
            embed.set_footer(text=f"Tienes {qty} en tu inventario")
            await message.channel.send(embed=embed)
        elif item == "anti_rob":
            embed = await activate_anti_rob(message.author, message.guild, qty)
            await message.channel.send(embed=embed)
        else:
            embed = discord.Embed(title="❌ No se puede usar", color=0xFF4444)
            embed.description = f"**{item_data['name']}** no tiene una acción de uso manual."
            await message.channel.send(embed=embed)

    # ,bet @usuario <cantidad>
    elif cmd == "bet":
        if not message.mentions:
            await message.channel.send("❌ Uso: `,bet @usuario <cantidad>`")
            return
        usuario = message.mentions[0]
        if usuario.id == message.author.id:
            await message.channel.send("❌ No puedes apostarte a ti mismo.")
            return
        if usuario.bot:
            await message.channel.send("❌ No puedes retar a un bot.")
            return
        remaining = [a for a in args if not a.startswith("<@")]
        if not remaining:
            await message.channel.send("❌ Uso: `,bet @usuario <cantidad>`")
            return
        try:
            cantidad = int(remaining[0])
        except ValueError:
            await message.channel.send("❌ La cantidad debe ser un número.")
            return
        if cantidad <= 0:
            await message.channel.send("❌ La apuesta debe ser mayor a 0.")
            return
        challenger_id = str(message.author.id)
        challenged_id = str(usuario.id)
        await get_or_create_user(challenger_id, message.author.name)
        await get_or_create_user(challenged_id, usuario.name)
        challenger_balance = await get_balance(challenger_id)
        if challenger_balance < cantidad:
            await message.channel.send(f"❌ No tienes suficientes monedas. Tienes **{challenger_balance:,}** 🪙.")
            return
        await update_balance(challenger_id, -cantidad)
        embed = discord.Embed(title="🎲 ¡Desafío de Apuesta!", color=0xE67E22)
        embed.description = (
            f"**{message.author.mention}** reta a **{usuario.mention}** a una apuesta.\n\n"
            f"💰 **En juego:** {cantidad:,} 🪙 cada uno → **bote total: {cantidad * 2:,}** 🪙\n\n"
            f"🎯 El ganador se lleva **todo**. ¡El azar decide!\n\n"
            f"⏳ Tienes **60 segundos** para aceptar o rechazar."
        )
        embed.set_footer(text=f"Solo {usuario.display_name} puede responder")
        view = BetView(
            challenger_id=challenger_id,
            challenged_id=challenged_id,
            amount=cantidad,
            challenger_name=message.author.display_name
        )
        sent = await message.channel.send(embed=embed, view=view, content=usuario.mention)
        view.message = sent

    # ,gift @usuario <item_id>
    elif cmd == "gift":
        if not message.mentions:
            await message.channel.send("❌ Uso: `,gift @usuario <item_id>`")
            return
        usuario = message.mentions[0]
        if usuario.id == message.author.id:
            await message.channel.send("❌ No puedes regalarte objetos a ti mismo.")
            return
        if usuario.bot:
            await message.channel.send("❌ No puedes regalarle a un bot.")
            return
        remaining = [a for a in args if not a.startswith("<@")]
        if not remaining:
            await message.channel.send("❌ Uso: `,gift @usuario <item_id>`")
            return
        item = normalize_shop_item_id(remaining[0])
        if item not in SHOP_ITEMS:
            ids = ", ".join(f"`{k}`" for k in SHOP_ITEMS.keys())
            await message.channel.send(f"❌ Objeto no encontrado. IDs válidos:\n{ids}")
            return
        sender_id = str(message.author.id)
        receiver_id = str(usuario.id)
        await get_or_create_user(sender_id, message.author.name)
        await get_or_create_user(receiver_id, usuario.name)
        qty = await get_item_quantity(sender_id, item)
        if qty == 0:
            embed = discord.Embed(title="❌ Sin Objeto", color=0xFF4444)
            embed.description = f"No tienes **{SHOP_ITEMS[item]['name']}** en tu inventario."
            await message.channel.send(embed=embed)
            return
        await remove_from_inventory(sender_id, item)
        await add_to_inventory(receiver_id, item)
        item_data = SHOP_ITEMS[item]
        embed = discord.Embed(title="🎁 ¡Regalo Enviado!", color=0x00FF88)
        embed.description = (
            f"**{message.author.mention}** le regaló **{item_data['name']}** a **{usuario.mention}**.\n\n"
            f"{item_data['description']}\n\nTe quedan **{qty - 1}** unidades en inventario."
        )
        await message.channel.send(embed=embed)

    # ,sell <item_id>
    elif cmd == "sell":
        await get_or_create_user(user_id, message.author.name)
        if not args:
            ids = ", ".join(f"`{k}`" for k in SHOP_ITEMS.keys())
            await message.channel.send(f"❌ Uso: `,sell <item_id>`\nIDs: {ids}")
            return
        item = normalize_shop_item_id(args[0])
        if item not in SHOP_ITEMS:
            ids = ", ".join(f"`{k}`" for k in SHOP_ITEMS.keys())
            await message.channel.send(f"❌ Objeto no encontrado. IDs válidos:\n{ids}")
            return
        qty = await get_item_quantity(user_id, item)
        if qty == 0:
            embed = discord.Embed(title="❌ Sin Objeto", color=0xFF4444)
            embed.description = f"No tienes **{SHOP_ITEMS[item]['name']}** en tu inventario."
            await message.channel.send(embed=embed)
            return
        item_data = SHOP_ITEMS[item]
        sell_price = item_data["price"] // 2
        await remove_from_inventory(user_id, item)
        await update_balance(user_id, sell_price)
        new_balance = await get_balance(user_id)
        embed = discord.Embed(title="💰 Objeto Vendido", color=0xFFD700)
        embed.description = (
            f"Vendiste **{item_data['name']}** por **{sell_price:,}** 🪙 (50% del precio original).\n\n"
            f"Saldo actual: **{new_balance:,}** 🪙\nTe quedan **{qty - 1}** unidades en inventario."
        )
        await message.channel.send(embed=embed)

    # ,abrirpaquete [tipo] / ,pack — abrir sobre de tarjetas de fútbol
    elif cmd in ("abrirpaquete", "pack", "paquete", "sobre"):
        await get_or_create_user(user_id, message.author.name)
        qty, name_text = parse_name_and_quantity(args)
        pack_key = resolve_pack(name_text) if name_text else "comun"
        if not pack_key:
            lines = "\n".join(
                f"{pt['emoji']} `,abrirpaquete {k}` — {pt['label']} · **{pt['price']:,}** 🪙"
                for k, pt in PACK_TYPES.items()
            )
            embed = discord.Embed(title="❌ Tipo de sobre inválido", color=0xFF4444,
                                  description=f"Tipos disponibles:\n{lines}")
            await message.channel.send(embed=embed)
            return
        embed, _ok = await _do_pack_purchase(message.author, pack_key, qty)
        await message.channel.send(embed=embed)

    # ,coleccion / ,album — ver colección de cartas
    elif cmd in ("coleccion", "album", "cartas", "miscartas"):
        # Support: ,coleccion  OR  ,coleccion @usuario
        target_member = message.mentions[0] if message.mentions else None
        target_id     = str(target_member.id) if target_member else user_id
        target_name   = target_member.display_name if target_member else message.author.display_name
        is_own        = target_id == user_id
        await get_or_create_user(target_id, target_name)
        rows = await _get_collection(target_id)
        if not rows:
            embed = discord.Embed(title="📦 Colección vacía", color=0x95A5A6)
            if is_own:
                embed.description = "Aún no tienes tarjetas. Usa `,abrirpaquete comun` para conseguir las primeras."
            else:
                embed.description = f"**{target_name}** aún no tiene tarjetas."
            await message.channel.send(embed=embed)
            return
        by_rarity: dict[str, list[tuple[str, int]]] = {r: [] for r in RARITY_CONFIG}
        total_cards  = sum(q for _, q in rows)
        unique_cards = len(rows)
        best_card_id = max((cid for cid, _ in rows if cid in FOOTBALL_CARDS),
                           key=lambda cid: FOOTBALL_CARDS[cid]["ovr"], default=None)
        for cid, qty in rows:
            c = FOOTBALL_CARDS.get(cid)
            if c:
                by_rarity[c["rarity"]].append((cid, qty))
        best_rarity_owned = next((r for r in RARITY_CONFIG if by_rarity[r]), "comun")
        embed = discord.Embed(
            title=f"⚽ Colección de {target_name}",
            color=RARITY_CONFIG[best_rarity_owned]["color"],
        )
        summary = f"🃏 **{unique_cards}** únicas · **{total_cards}** total"
        if best_card_id:
            bc = FOOTBALL_CARDS[best_card_id]
            summary += f"\n⭐ Mejor carta: {RARITY_CONFIG[bc['rarity']]['emoji']} **{bc['name']}** OVR {bc['ovr']}"
        embed.description = summary + "\n\u200b"
        for rarity in RARITY_CONFIG:
            cards = by_rarity[rarity]
            if not cards:
                continue
            rc = RARITY_CONFIG[rarity]
            lines = [_card_line(cid, qty) for cid, qty in
                     sorted(cards, key=lambda x: -FOOTBALL_CARDS[x[0]]["ovr"])]
            embed.add_field(
                name=f"{rc['emoji']} {rc['label']} ({len(cards)})",
                value="\n".join(lines) or "_Ninguna_",
                inline=False,
            )
        if not is_own and target_member:
            embed.set_footer(text=f"💡 Usa ,intercambiar @{target_name} para proponer un intercambio")
        await message.channel.send(embed=embed)

    # ,infocartas — tipos de sobres y precios
    # ,vender <carta> <precio> — publicar carta en el mercado
    elif cmd in ("vender", "sell"):
        await get_or_create_user(user_id, message.author.name)
        if len(args) < 2:
            await message.channel.send("❌ Uso: `,vender <carta> <precio>`  Ej: `,vender messi 50000`")
            return
        carta = args[0].lower()
        try:
            precio = int(args[1].replace(",", "").replace(".", ""))
        except ValueError:
            await message.channel.send("❌ El precio debe ser un número. Ej: `,vender messi 50000`")
            return
        if carta not in FOOTBALL_CARDS:
            await message.channel.send(f"❌ Carta `{carta}` no existe. Revisa los IDs en `,coleccion`.")
            return
        if precio < 100:
            await message.channel.send("❌ El precio mínimo es **100** 🪙.")
            return
        qty = await _card_qty(user_id, carta)
        if qty < 1:
            c = FOOTBALL_CARDS[carta]
            await message.channel.send(f"❌ No tienes la carta **{c['name']}**.")
            return
        count = await _market_count_seller(user_id)
        if count >= MAX_LISTINGS_PER_USER:
            await message.channel.send(
                f"❌ Ya tienes **{MAX_LISTINGS_PER_USER}** cartas en venta. Cancela alguna primero.")
            return
        await _remove_card(user_id, carta)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO card_market (seller_id, card_id, price, ts) VALUES (?,?,?,?)",
                (user_id, carta, precio, datetime.utcnow().isoformat())
            )
            await db.commit()
        c = FOOTBALL_CARDS[carta]
        rc = RARITY_CONFIG[c["rarity"]]
        embed = discord.Embed(title="🏪 ¡Carta publicada!", color=rc["color"])
        embed.description = (
            f"➤ {_card_line(carta)}\n\n"
            f"💰 Precio: **{precio:,}** 🪙\n"
            f"La carta fue retirada de tu colección hasta que se venda o la canceles."
        )
        embed.set_footer(text="Cancela con: ,cancelarventa <id>")
        await message.channel.send(embed=embed)

    # ,mercado [rareza] — ver cartas en venta
    elif cmd in ("mercado", "market", "tienda"):
        rarity_raw = args[0].lower() if args else ""
        rarity_key = _PACK_ALIASES.get(rarity_raw, "") if rarity_raw else ""
        listings = await _market_listings(rarity_key)
        title = "🏪 Mercado de Cartas"
        if rarity_key:
            rc = RARITY_CONFIG[rarity_key]
            title += f" — {rc['emoji']} {rc['label']}"
        embed = _market_embed(listings, title)
        embed.set_footer(text="Comprar: ,comprar <id>  •  Vender: ,vender <carta> <precio>")
        await message.channel.send(embed=embed)

    # ,comprar <id> — comprar carta del mercado
    elif cmd in ("comprar", "buy"):
        await get_or_create_user(user_id, message.author.name)
        if not args:
            await message.channel.send("❌ Uso: `,comprar <id>`  Ej: `,comprar 5`")
            return
        try:
            lid = int(args[0].lstrip("#"))
        except ValueError:
            await message.channel.send("❌ El ID debe ser un número. Ej: `,comprar 5`")
            return
        listing = await _market_get_listing(lid)
        if not listing:
            await message.channel.send(f"❌ La publicación **#{lid}** no existe o ya fue vendida.")
            return
        _lid, seller_id, card_id, price, ts = listing
        if seller_id == user_id:
            await message.channel.send("❌ No puedes comprar tu propia carta.")
            return
        bal = await get_balance(user_id)
        if bal < price:
            await message.channel.send(
                f"❌ Necesitas **{price:,}** 🪙 pero tienes **{bal:,}** 🪙.")
            return
        await _market_delete_listing(_lid)
        await update_balance(user_id, -price)
        await update_balance(seller_id, price)
        await _add_card(user_id, card_id)
        c = FOOTBALL_CARDS[card_id]
        rc = RARITY_CONFIG[c["rarity"]]
        embed = discord.Embed(title="🎉 ¡Compra exitosa!", color=rc["color"])
        embed.description = (
            f"➤ {_card_line(card_id)}\n\n"
            f"💸 Pagaste: **{price:,}** 🪙\n"
            f"La carta fue añadida a tu colección."
        )
        new_bal = await get_balance(user_id)
        embed.set_footer(text=f"Saldo restante: {new_bal:,} 🪙")
        await message.channel.send(embed=embed)
        try:
            seller = await client.fetch_user(int(seller_id))
            dm_embed = discord.Embed(title="💰 ¡Vendiste una carta!", color=0x2ECC71)
            dm_embed.description = (
                f"**{message.author.display_name}** compró tu:\n"
                f"➤ {_card_line(card_id)}\n\n"
                f"Recibiste **{price:,}** 🪙 en tu balance."
            )
            await seller.send(embed=dm_embed)
        except Exception:
            pass

    # ,cancelarventa <id> — retirar carta del mercado
    elif cmd in ("cancelarventa", "cancelventa", "retirar"):
        if not args:
            await message.channel.send("❌ Uso: `,cancelarventa <id>`  Ej: `,cancelarventa 5`")
            return
        try:
            lid = int(args[0].lstrip("#"))
        except ValueError:
            await message.channel.send("❌ El ID debe ser un número.")
            return
        card_id, error = await cancel_market_listing(user_id, lid)
        if error:
            await message.channel.send(f"❌ {error}")
            return
        c = FOOTBALL_CARDS[card_id]
        embed = discord.Embed(title="↩️ Venta cancelada", color=0x95A5A6)
        embed.description = f"➤ {_card_line(card_id)}\n\nLa carta fue devuelta a tu colección."
        await message.channel.send(embed=embed)

    # ,misventas — ver tus cartas en venta
    elif cmd in ("misventas", "mylistings", "ventas"):
        await get_or_create_user(user_id, message.author.name)
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT id, card_id, price, ts FROM card_market WHERE seller_id=? ORDER BY id",
                (user_id,)
            ) as cur:
                rows = await cur.fetchall()
        if not rows:
            embed = discord.Embed(title="📦 Sin ventas activas", color=0x95A5A6,
                                   description="No tienes cartas en el mercado.\nUsa `,vender <carta> <precio>` para publicar una.")
            await message.channel.send(embed=embed)
            return
        embed = discord.Embed(title="🏷️ Mis cartas en venta", color=0xF39C12)
        lines = []
        for lid, card_id, price, ts in rows:
            c = FOOTBALL_CARDS.get(card_id, {})
            rc = RARITY_CONFIG.get(c.get("rarity", "comun"), RARITY_CONFIG["comun"])
            lines.append(f"`#{lid}` {rc['emoji']} **{c.get('name','?')}** — **{price:,}** 🪙")
        embed.description = "\n".join(lines)
        embed.set_footer(text=f"{len(rows)}/{MAX_LISTINGS_PER_USER} slots · ,cancelarventa <id> para retirar")
        await message.channel.send(embed=embed)

    elif cmd in ("infocartas", "infopaquete", "probabilidades", "sobres"):
        embed = discord.Embed(title="⚽ Sobres de Tarjetas de Fútbol", color=0x3498DB)
        embed.description = (
            f"📦 **{CARDS_PER_PACK} cartas** por sobre · **{len(FOOTBALL_CARDS)} cartas** en total\n"
            "🎲 Porcentajes por carta; las tres se sortean independientemente. No hay rarezas garantizadas.\n"
        )
        for pack_key, pt in PACK_TYPES.items():
            embed.add_field(
                name=f"{pt['emoji']} {pt['label']} — {pt['price']:,} 🪙",
                value=_format_pack_probabilities(pt),
                inline=False,
            )
        embed.set_footer(text="Uso: ,abrirpaquete <tipo>  •  Ej: ,abrirpaquete raro")
        await message.channel.send(embed=embed)

    # ,intercambiar @usuario <mi_carta> [<su_carta>] — proponer intercambio
    elif cmd in ("intercambiar", "trade", "cambiar"):
        await get_or_create_user(user_id, message.author.name)
        if not message.mentions:
            await message.channel.send("❌ Uso: `,intercambiar @usuario <mi_carta> [<su_carta>]`")
            return
        target = message.mentions[0]
        if target.bot or str(target.id) == user_id:
            await message.channel.send("❌ No puedes intercambiar contigo mismo ni con un bot.")
            return
        # args after stripping the mention
        clean = message.content.split()
        # remove prefix+cmd and any mention tokens (@xxx)
        card_args = [a for a in clean[2:] if not a.startswith("<@")]
        if not card_args:
            await message.channel.send("❌ Uso: `,intercambiar @usuario <mi_carta> [<su_carta>]`")
            return
        mi_carta = card_args[0].lower()
        su_carta = card_args[1].lower() if len(card_args) > 1 else ""
        if mi_carta not in FOOTBALL_CARDS:
            await message.channel.send(f"❌ Carta `{mi_carta}` no existe. Revisa los IDs en `,coleccion`.")
            return
        if su_carta and su_carta not in FOOTBALL_CARDS:
            await message.channel.send(f"❌ Carta `{su_carta}` no existe.")
            return
        to_uid = str(target.id)
        await get_or_create_user(to_uid, target.name)
        my_qty = await _card_qty(user_id, mi_carta)
        if my_qty < 1:
            await message.channel.send(
                f"❌ No tienes la carta **{FOOTBALL_CARDS[mi_carta]['name']}**.")
            return
        if su_carta:
            their_qty = await _card_qty(to_uid, su_carta)
            if their_qty < 1:
                await message.channel.send(
                    f"❌ **{target.display_name}** no tiene la carta **{FOOTBALL_CARDS[su_carta]['name']}**.")
                return
        fc = FOOTBALL_CARDS[mi_carta]
        rc_f = RARITY_CONFIG[fc["rarity"]]
        desc  = f"**{message.author.display_name}** te ofrece:\n"
        desc += f"➤ {_card_line(mi_carta)}\n\n"
        if su_carta:
            desc += f"A cambio pide tu:\n➤ {_card_line(su_carta)}\n\n"
        else:
            desc += "_Sin pedir nada a cambio (regalo)_\n\n"
        desc += "⏱️ Tienes **5 minutos** para responder."
        embed = discord.Embed(
            title=f"🤝 Propuesta de Intercambio para {target.display_name}",
            color=rc_f["color"], description=desc)
        view = TradeView(user_id, to_uid, mi_carta, su_carta,
                         message.author.display_name, target.display_name)
        await message.channel.send(
            content=f"{target.mention} tienes una oferta de intercambio:",
            embed=embed, view=view)

    # ,historial — últimas 10 apuestas
    elif cmd in ("historial", "history", "stats"):
        await get_or_create_user(user_id, message.author.name)
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT game, amount_bet, net, ts FROM bet_history WHERE user_id=? ORDER BY id DESC LIMIT 10",
                (user_id,)
            ) as cur:
                rows = await cur.fetchall()
            async with db.execute(
                "SELECT COUNT(*), SUM(amount_bet), SUM(net) FROM bet_history WHERE user_id=?",
                (user_id,)
            ) as cur:
                stats = await cur.fetchone()

        embed = discord.Embed(title=f"📊 Historial de {message.author.display_name}", color=0x3498DB)
        if not rows:
            embed.description = "No tienes apuestas registradas todavía.\nJuega a la ruleta o slots para empezar."
        else:
            lines = []
            for game, amount_bet, net, ts in rows:
                try:
                    dt = datetime.fromisoformat(ts)
                    date_str = dt.strftime("%d/%m %H:%M")
                except Exception:
                    date_str = "—"
                icon = "✅" if net >= 0 else "❌"
                net_str = f"+{net:,}" if net >= 0 else f"{net:,}"
                lines.append(f"{icon} **{game}** — {amount_bet:,} 🪙 → **{net_str}** 🪙 _{date_str}_")
            embed.description = "\n".join(lines)

            total_games, total_wagered, total_net = stats
            total_wagered = total_wagered or 0
            total_net = total_net or 0
            net_color = "🟢" if total_net >= 0 else "🔴"
            total_net_str = f"+{total_net:,}" if total_net >= 0 else f"{total_net:,}"
            embed.add_field(
                name="📈 Estadísticas totales",
                value=(
                    f"🎲 Partidas jugadas: **{total_games}**\n"
                    f"💸 Total apostado: **{total_wagered:,}** 🪙\n"
                    f"{net_color} Balance neto: **{total_net_str}** 🪙"
                ),
                inline=False,
            )
        await message.channel.send(embed=embed)

    # ,lroulette [segundos] — ruleta en vivo con temporizador
    elif cmd in ("lroulette", "liveroulette", "ruleta"):
        await get_or_create_user(user_id, message.author.name)
        tiempo = 60
        if args:
            try:
                t = int(args[0])
                if 10 <= t <= 120:
                    tiempo = t
                else:
                    await message.channel.send("❌ El tiempo debe estar entre 10 y 120 segundos.")
                    return
            except ValueError:
                pass
        view = LiveRouletteView(
            host_id=user_id,
            host_name=message.author.display_name,
            timeout_secs=tiempo,
        )
        sent = await message.channel.send(embed=view.make_embed(), view=view)
        view.message = sent

    # ,help / ,ayuda
    elif cmd in ("help", "ayuda", "comandos"):
        embed = discord.Embed(
            title="🎰 Casino Bot — Comandos",
            description="Todos los comandos funcionan con `,` o con `/`.",
            color=0xE91E63
        )
        embed.add_field(
            name="💰 Economía",
            value=(
                "`,balance` `,daily` `,dep` `,withdraw` `,pay` `,lb`"
            ),
            inline=False
        )
        embed.add_field(
            name="🎰 Juegos",
            value=(
                "`,slots` `,roulette` `,bj` `,coinflip` `,crash`\n"
                "Ruleta: `red` `black` `even` `odd` `1st` `2nd` `3rd`"
            ),
            inline=False
        )
        embed.add_field(
            name="⚔️ PvP",
            value="`,duel @u cantidad` `,bet @u cantidad` `,rob @u` `,torneo`",
            inline=False
        )
        embed.add_field(
            name="🥊 Luchadores",
            value="`,fighters` `,buyfighter` `,myfighter` `,fight @u` `,ftorneo` `,addpuntos`",
            inline=False
        )
        embed.add_field(
            name="🛍️ Tienda",
            value="`,shop` `,buy` `,inventory` `,use` `,gift` `,sell`",
            inline=False
        )
        embed.add_field(
            name="📋 Misc",
            value="`,missions` `,work` `,slut` `,crime` `,lottery`",
            inline=False
        )
        embed.set_footer(text="🏦 El banco es seguro contra robos  •  Casino Bot")
        await message.channel.send(embed=embed)


# =====================================================================
#  PRÉSTAMOS: intereses, cuotas semanales, cobro automático y recargos
#  Comandos: /loan /debt /payloan  (prefijo: ,loan ,debt ,payloan)
# =====================================================================
import calendar as _loan_calendar
import math as _loan_math
from typing import Optional as _LoanOptional

# ===================== CONFIGURACION (cambia estos numeros) =====================
LOAN_INTEREST_PERCENT = 25        # interes base (por cada tramo)
LOAN_TIER_SIZE = 5_000_000        # cada tramo de este monto suma otro LOAN_INTEREST_PERCENT
LOAN_WEEKLY_PERCENT = 5           # % de la deuda total que se paga en cada cuota
LOAN_MIN = 1_000             # prestamo minimo
LOAN_MAX = 150_000_000       # prestamo maximo
LOAN_LATE_FEE_PERCENT = 10        # recargo sobre la parte de la cuota que no se pudo cobrar
LOAN_PERIOD = timedelta(days=7)   # cada cuanto se cobra (para probar: timedelta(minutes=2))
LOAN_CHECK_SECONDS = 60           # cada cuanto revisa el bot si hay cuotas vencidas
# ================================================================================

def _loan_db():
    return aiosqlite.connect(DB_PATH)


# ------------------------------------------------------------------ utilidades
def loan_interest_percent(amount: int) -> int:
    # hasta 5M = 25%, hasta 10M = 50%, hasta 15M = 75%, etc.
    tiers = max(1, _loan_math.ceil(amount / LOAN_TIER_SIZE))
    return tiers * LOAN_INTEREST_PERCENT


def loan_calc_terms(amount: int):
    interest = _loan_math.ceil(amount * loan_interest_percent(amount) / 100)
    total = amount + interest
    installment = max(1, _loan_math.ceil(total * LOAN_WEEKLY_PERCENT / 100))
    payments = _loan_math.ceil(total / installment)
    return interest, total, installment, payments


def loan_parse_amount(text) -> _LoanOptional[int]:
    t = str(text).strip().lower().replace(",", "").replace("_", "")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", t):  # 50.000 -> 50000
        t = t.replace(".", "")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([km]?)", t)
    if not m:
        return None
    mult = {"": 1, "k": 1_000, "m": 1_000_000}[m.group(2)]
    return int(float(m.group(1)) * mult)


def _loan_period_text() -> str:
    if LOAN_PERIOD == timedelta(days=7):
        return "semana"
    return f"{max(1, int(LOAN_PERIOD.total_seconds() // 60))} min"


def _loan_ts(iso: str) -> int:
    return _loan_calendar.timegm(datetime.fromisoformat(iso).timetuple())


def _loan_err(title: str, message: str) -> discord.Embed:
    return discord.Embed(title=f"❌ {title}", description=message, color=0xFF4444)


# ------------------------------------------------------------------ embeds
def loan_info_embed() -> discord.Embed:
    interest, total, installment, payments = loan_calc_terms(50_000)
    embed = discord.Embed(title="🏦 Préstamos del Casino", color=0x3498DB)
    embed.description = (
        f"Pide entre **{LOAN_MIN:,}** y **{LOAN_MAX:,}** 🪙 con `/loan <cantidad>`.\n\n"
        f"• Interés: **{LOAN_INTEREST_PERCENT}%** por cada **{LOAN_TIER_SIZE:,}** 🪙 prestados "
        f"(hasta {LOAN_TIER_SIZE:,} = {LOAN_INTEREST_PERCENT}%, hasta {LOAN_TIER_SIZE*2:,} = {LOAN_INTEREST_PERCENT*2}%, "
        f"hasta {LOAN_TIER_SIZE*3:,} = {LOAN_INTEREST_PERCENT*3}%...)\n"
        f"• Cada **{_loan_period_text()}** se cobra una cuota de **{LOAN_WEEKLY_PERCENT}%** de la deuda total\n"
        f"• Si no hay fondos, se cobra lo que haya y se suma un recargo de **{LOAN_LATE_FEE_PERCENT}%** "
        f"sobre lo no pagado\n"
        f"• Solo puedes tener 1 préstamo a la vez\n"
        f"• Puedes pagar antes con `/payloan`\n\n"
        f"**Ejemplo:** pides **50,000** → devuelves **{total:,}** "
        f"(**{payments}** pagos de **{installment:,}**)."
    )
    return embed


def loan_terms_embed(amount: int) -> discord.Embed:
    interest, total, installment, payments = loan_calc_terms(amount)
    embed = discord.Embed(title="🏦 Confirma tu préstamo", color=0x3498DB)
    embed.description = (
        f"💵 Recibes: **{amount:,}** 🪙\n"
        f"📈 Interés ({loan_interest_percent(amount)}%): **{interest:,}** 🪙\n"
        f"🧾 Total a devolver: **{total:,}** 🪙\n\n"
        f"📅 Cuota cada **{_loan_period_text()}**: **{installment:,}** 🪙 ({LOAN_WEEKLY_PERCENT}%)\n"
        f"🔢 Número de pagos: **{payments}**\n\n"
        f"Se descuenta de tu cartera y, si no alcanza, de tu banco."
    )
    return embed


def loan_debt_embed(loan: dict) -> discord.Embed:
    total, remaining = loan["total_due"], loan["remaining"]
    paid = max(0, total - remaining)
    ratio = min(1.0, paid / total) if total else 1.0
    filled = int(ratio * 10)
    bar = "█" * filled + "░" * (10 - filled)
    next_payment = min(loan["installment"], remaining)
    due = _loan_ts(loan["next_due"])
    embed = discord.Embed(title="📋 Tu deuda", color=0xE67E22)
    embed.description = f"`[{bar}]` **{int(ratio * 100)}%** pagado"
    embed.add_field(name="💰 Prestado", value=f"**{loan['principal']:,}** 🪙", inline=True)
    embed.add_field(name="🧾 Total a devolver", value=f"**{total:,}** 🪙", inline=True)
    embed.add_field(name="⏳ Te falta", value=f"**{remaining:,}** 🪙", inline=True)
    embed.add_field(
        name="📅 Próxima cuota",
        value=f"**{next_payment:,}** 🪙 · <t:{due}:R> (<t:{due}:f>)",
        inline=False,
    )
    if loan["missed"]:
        embed.add_field(name="⚠️ Cuotas falladas", value=f"**{loan['missed']}**", inline=True)
    embed.set_footer(text="Paga antes con /payloan · /payloan all para saldar todo")
    return embed


# ------------------------------------------------------------------ base de datos
async def loan_init_table():
    async with _loan_db() as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS loans (
                user_id TEXT PRIMARY KEY,
                principal INTEGER NOT NULL,
                total_due INTEGER NOT NULL,
                remaining INTEGER NOT NULL,
                installment INTEGER NOT NULL,
                next_due TEXT NOT NULL,
                missed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        await db.commit()


async def _loan_get_row(db, user_id: str) -> _LoanOptional[dict]:
    async with db.execute(
        "SELECT principal, total_due, remaining, installment, next_due, missed "
        "FROM loans WHERE user_id = ?",
        (user_id,),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    return dict(zip(("principal", "total_due", "remaining", "installment", "next_due", "missed"), row))


async def loan_get(user_id: str) -> _LoanOptional[dict]:
    async with _loan_db() as db:
        return await _loan_get_row(db, user_id)


async def _loan_take(db, user_id: str, amount: int) -> int:
    """Descuenta hasta `amount`: primero cartera, luego banco. Devuelve lo cobrado."""
    async with db.execute(
        "SELECT balance, COALESCE(bank, 0) FROM users WHERE user_id = ?", (user_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return 0
    wallet, bank = row[0] or 0, row[1] or 0
    from_wallet = min(wallet, amount)
    from_bank = min(bank, amount - from_wallet)
    if from_wallet or from_bank:
        await db.execute(
            "UPDATE users SET balance = balance - ?, bank = COALESCE(bank, 0) - ? WHERE user_id = ?",
            (from_wallet, from_bank, user_id),
        )
    return from_wallet + from_bank


# ------------------------------------------------------------------ logica principal
async def loan_create(user_id: str, username: str, amount: int) -> discord.Embed:
    await get_or_create_user(user_id, username)
    if not LOAN_MIN <= amount <= LOAN_MAX:
        return _loan_err("Cantidad no válida", f"El préstamo debe estar entre **{LOAN_MIN:,}** y **{LOAN_MAX:,}** 🪙.")
    interest, total, installment, payments = loan_calc_terms(amount)
    now = datetime.utcnow()
    async with _loan_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            if await _loan_get_row(db, user_id):
                await db.rollback()
                return _loan_err("Ya tienes una deuda", "Termina de pagar tu préstamo actual antes de pedir otro. Mira `/debt`.")
            async with db.execute(
                "SELECT COALESCE(balance, 0) FROM users WHERE user_id = ?", (user_id,)
            ) as cur:
                wallet_row = await cur.fetchone()
            wallet = wallet_row[0] if wallet_row else 0
            if wallet + amount > MAX_BALANCE:
                await db.rollback()
                return _loan_err(
                    "Cartera llena",
                    "No cabe el préstamo completo en tu cartera. Deposita monedas en el banco y vuelve a intentarlo.",
                )
            await db.execute(
                "INSERT INTO loans (user_id, principal, total_due, remaining, installment, "
                "next_due, missed, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                (user_id, amount, total, total, installment, (now + LOAN_PERIOD).isoformat(), now.isoformat()),
            )
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    due = int(_loan_calendar.timegm((now + LOAN_PERIOD).timetuple()))
    embed = discord.Embed(title="✅ ¡Préstamo aprobado!", color=0x00FF88)
    embed.description = (
        f"Recibiste **{amount:,}** 🪙 en tu cartera.\n"
        f"Debes devolver **{total:,}** 🪙 en **{payments}** pagos de **{installment:,}** 🪙.\n\n"
        f"📅 Primera cuota: <t:{due}:R>\n"
        f"Usa `/debt` para ver tu deuda y `/payloan` para pagar antes."
    )
    return embed


async def loan_pay(user_id: str, username: str, text: _LoanOptional[str]) -> discord.Embed:
    await get_or_create_user(user_id, username)
    async with _loan_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            loan = await _loan_get_row(db, user_id)
            if loan is None:
                await db.rollback()
                return _loan_err("Sin deuda", "No tienes ningún préstamo activo. 🎉")
            remaining = loan["remaining"]
            t = (text or "").strip().lower()
            if not t:
                amount = min(loan["installment"], remaining)
            elif t in ("all", "todo", "todas", "saldar"):
                amount = remaining
            else:
                parsed = loan_parse_amount(t)
                if parsed is None or parsed <= 0:
                    await db.rollback()
                    return _loan_err("Cantidad no válida", "Escribe un número, `all` para saldar todo, o déjalo vacío para pagar una cuota.")
                amount = min(parsed, remaining)

            async with db.execute(
                "SELECT balance, COALESCE(bank, 0) FROM users WHERE user_id = ?", (user_id,)
            ) as cur:
                row = await cur.fetchone()
            available = ((row[0] or 0) + (row[1] or 0)) if row else 0
            if available < amount:
                await db.rollback()
                return _loan_err(
                    "Saldo insuficiente",
                    f"Quieres pagar **{amount:,}** 🪙 pero entre cartera y banco tienes **{available:,}** 🪙.",
                )

            taken = await _loan_take(db, user_id, amount)
            new_remaining = remaining - taken
            if new_remaining <= 0:
                await db.execute("DELETE FROM loans WHERE user_id = ?", (user_id,))
                closed, next_due = True, None
            else:
                closed = False
                cycles = taken // loan["installment"]
                next_due = (datetime.fromisoformat(loan["next_due"]) + LOAN_PERIOD * cycles).isoformat()
                await db.execute(
                    "UPDATE loans SET remaining = ?, next_due = ? WHERE user_id = ?",
                    (new_remaining, next_due, user_id),
                )
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    if closed:
        return discord.Embed(
            title="🎉 ¡Deuda saldada!",
            description=f"Pagaste **{taken:,}** 🪙 y ya no debes nada. ¡Gracias por ser buen cliente!",
            color=0x00FF88,
        )
    embed = discord.Embed(title="💸 Pago realizado", color=0x00FF88)
    embed.description = (
        f"Pagaste **{taken:,}** 🪙.\n"
        f"Te faltan **{new_remaining:,}** 🪙.\n"
        f"📅 Próxima cuota: <t:{_loan_ts(next_due)}:R>"
    )
    return embed


async def _loan_charge(user_id: str) -> _LoanOptional[discord.Embed]:
    """Cobro automatico de la cuota vencida."""
    async with _loan_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            loan = await _loan_get_row(db, user_id)
            if loan is None or datetime.fromisoformat(loan["next_due"]) > datetime.utcnow():
                await db.rollback()
                return None
            due_amount = min(loan["installment"], loan["remaining"])
            taken = await _loan_take(db, user_id, due_amount)
            remaining = loan["remaining"] - taken
            missed = loan["missed"]
            fee = 0
            if taken < due_amount:
                missed += 1
                fee = _loan_math.ceil((due_amount - taken) * LOAN_LATE_FEE_PERCENT / 100)
                remaining += fee
            now = datetime.utcnow()
            if remaining <= 0:
                await db.execute("DELETE FROM loans WHERE user_id = ?", (user_id,))
                next_due = None
            else:
                nd = datetime.fromisoformat(loan["next_due"]) + LOAN_PERIOD
                if nd <= now:
                    nd = now + LOAN_PERIOD
                next_due = nd.isoformat()
                await db.execute(
                    "UPDATE loans SET remaining = ?, missed = ?, next_due = ? WHERE user_id = ?",
                    (remaining, missed, next_due, user_id),
                )
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    if remaining <= 0:
        return discord.Embed(
            title="🎉 ¡Última cuota cobrada!",
            description=f"Se cobraron **{taken:,}** 🪙 y tu deuda quedó saldada.",
            color=0x00FF88,
        )
    if taken >= due_amount:
        embed = discord.Embed(title="📅 Cuota cobrada", color=0x3498DB)
        embed.description = (
            f"Se cobraron **{taken:,}** 🪙 de tu préstamo.\n"
            f"Te faltan **{remaining:,}** 🪙.\n"
            f"Próxima cuota: <t:{_loan_ts(next_due)}:R>"
        )
        return embed
    embed = discord.Embed(title="⚠️ Cuota no cubierta", color=0xFF4444)
    embed.description = (
        f"Solo se pudieron cobrar **{taken:,}** de **{due_amount:,}** 🪙.\n"
        f"Recargo por mora: **+{fee:,}** 🪙.\n"
        f"Ahora debes **{remaining:,}** 🪙. Próximo intento: <t:{_loan_ts(next_due)}:R>.\n"
        f"Paga con `/payloan` para evitar más recargos."
    )
    return embed


async def _loan_dm(user_id: str, embed: discord.Embed):
    try:
        user = client.get_user(int(user_id)) or await client.fetch_user(int(user_id))
        await user.send(embed=embed)
    except Exception:
        pass  # DMs cerrados: no pasa nada


async def _loan_process_due():
    async with _loan_db() as db:
        async with db.execute("SELECT user_id, next_due FROM loans") as cur:
            rows = await cur.fetchall()
    now = datetime.utcnow()
    for user_id, next_due in rows:
        try:
            if datetime.fromisoformat(next_due) > now:
                continue
        except ValueError:
            pass
        embed = await _loan_charge(user_id)
        if embed is not None:
            await _loan_dm(user_id, embed)


async def _loan_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            await for_each_guild(_loan_process_due)
        except Exception as exc:  # el bucle nunca debe morir
            print(f"Error en el bucle de préstamos: {exc}")
        await asyncio.sleep(LOAN_CHECK_SECONDS)


# ------------------------------------------------------------------ interfaz
class LoanConfirmView(GuildView):
    def __init__(self, owner_id: str, amount: int):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.amount = amount

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.owner_id:
            await interaction.response.send_message("Este préstamo es de otra persona.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Aceptar préstamo", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        embed = await loan_create(self.owner_id, interaction.user.name, self.amount)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(title="Préstamo cancelado", color=0x888888), view=None
        )


# ------------------------------------------------------------------ prefijo
async def loan_handle_prefix(message: discord.Message, cmd: str, args: list) -> bool:
    """Devuelve True si el comando era de prestamos (asi el bot no sigue buscando)."""
    uid = str(message.author.id)
    name = message.author.name

    if cmd in ("loan", "prestamo", "préstamo"):
        if not args:
            await message.channel.send(embed=loan_info_embed())
            return True
        amount = loan_parse_amount(args[0])
        if amount is None or not LOAN_MIN <= amount <= LOAN_MAX:
            await message.channel.send(
                embed=_loan_err("Cantidad no válida", f"Usa `,loan <cantidad>` entre **{LOAN_MIN:,}** y **{LOAN_MAX:,}** 🪙.")
            )
            return True
        await get_or_create_user(uid, name)
        if await loan_get(uid):
            await message.channel.send(
                embed=_loan_err("Ya tienes una deuda", "Termina de pagar tu préstamo actual antes de pedir otro. Mira `,debt`.")
            )
            return True
        await message.channel.send(embed=loan_terms_embed(amount), view=LoanConfirmView(uid, amount))
        return True

    if cmd in ("debt", "deuda"):
        loan = await loan_get(uid)
        if loan is None:
            await message.channel.send(embed=_loan_err("Sin deuda", "No tienes ningún préstamo activo. 🎉"))
        else:
            await message.channel.send(embed=loan_debt_embed(loan))
        return True

    if cmd in ("payloan", "pagardeuda", "pagarprestamo"):
        embed = await loan_pay(uid, name, args[0] if args else None)
        await message.channel.send(embed=embed)
        return True

    return False


# ------------------------------------------------------------------ conexion con el bot


@tree.command(name="loan", description="Pide un préstamo al banco del casino (con intereses y pagos semanales)")
@app_commands.describe(cantidad=f"Cuánto quieres pedir ({LOAN_MIN:,} a {LOAN_MAX:,}). Vacío = ver condiciones")
async def loan_command(
    interaction: discord.Interaction,
    cantidad: _LoanOptional[app_commands.Range[int, LOAN_MIN, LOAN_MAX]] = None,
):
    if cantidad is None:
        await interaction.response.send_message(embed=loan_info_embed())
        return
    uid = str(interaction.user.id)
    await get_or_create_user(uid, interaction.user.name)
    if await loan_get(uid):
        await interaction.response.send_message(
            embed=_loan_err("Ya tienes una deuda", "Termina de pagar tu préstamo actual antes de pedir otro. Mira `/debt`."),
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        embed=loan_terms_embed(cantidad), view=LoanConfirmView(uid, cantidad), ephemeral=True
    )

@tree.command(name="debt", description="Mira tu deuda, lo que te falta y cuándo es tu próxima cuota")
async def debt_command(interaction: discord.Interaction):
    loan = await loan_get(str(interaction.user.id))
    if loan is None:
        await interaction.response.send_message(
            embed=_loan_err("Sin deuda", "No tienes ningún préstamo activo. 🎉"), ephemeral=True
        )
    else:
        await interaction.response.send_message(embed=loan_debt_embed(loan))

@tree.command(name="payloan", description="Paga tu préstamo: una cuota, una cantidad, o todo")
@app_commands.describe(cantidad="Monto a pagar, o 'all' para saldar todo. Vacío = una cuota")
async def payloan_command(interaction: discord.Interaction, cantidad: _LoanOptional[str] = None):
    embed = await loan_pay(str(interaction.user.id), interaction.user.name, cantidad)
    await interaction.response.send_message(embed=embed)


# =====================================================================
#  EXTRAS V2: prestamos/mercado de roles, carcel, logros, /top semanal,
#  clanes, evento de doble collect y mines.
#  Todos los numeros que puedes querer cambiar estan aqui arriba.
# =====================================================================
# ----- roles prestados / mercado de roles
ROLE_LOAN_MAX_DAYS = 30           # maximo de dias que se puede prestar o alquilar un rol
ROLE_LOAN_CHECK_SECONDS = 30      # cada cuanto revisa el bot si hay prestamos vencidos
ROLE_MARKET_FEE_PERCENT = 5       # comision del bot en ventas/alquileres del mercado de roles

# ----- carcel (cuando te atrapan robando)
JAIL_BASE_MINUTES = 10            # minutos de carcel la primera vez
JAIL_EXTRA_MINUTES_PER_STRIKE = 5 # minutos extra por cada captura seguida
JAIL_MAX_MINUTES = 60
JAIL_STRIKE_RESET_HOURS = 24      # sin caer en este tiempo, el contador de reincidencia se reinicia
JAIL_BAIL_PER_MINUTE = 5_000_000  # fianza = minutos que faltan x esto
JAIL_BLOCKED_COMMANDS = {         # comandos slash bloqueados mientras estas preso
    "rob", "slots", "roulette", "ruleta-en-vivo", "blackjack", "crash", "mines", "hilo",
    "coinflip", "duel", "bet", "fight", "ftorneo",
}
JAIL_BLOCKED_PREFIX = {           # lo mismo para los comandos con coma
    "rob", "slots", "slot", "tragamonedas", "roulette", "blackjack", "bj", "crash", "mines", "hilo",
    "coinflip", "cf", "duel", "bet", "fight", "ftorneo", "lroulette", "liveroulette", "ruleta",
}

# ----- ranking semanal (se reinicia cada lunes 00:00 UTC)
WEEKLY_PRIZES = (300_000_000, 150_000_000, 75_000_000)   # premios 1º, 2º y 3º
WEEKLY_CHECK_SECONDS = 60

# ----- clanes
CLAN_CREATE_COST = 50_000_000
CLAN_MAX_MEMBERS = 10
CLAN_NAME_RE = re.compile(r"[A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ _\-]{3,20}")
CLAN_MISSIONS = {                 # misiones semanales del clan; el premio va al banco del clan
    "jugadas":  {"name": "🎲 Apostadores",        "key": "plays",       "goal": 150, "reward": 300_000_000,
                 "desc": "Jueguen 150 partidas entre todos (slots, ruleta, crash, mines)"},
    "robos":    {"name": "🦹 Banda de ladrones",  "key": "rob_success", "goal": 10,  "reward": 200_000_000,
                 "desc": "Consigan 10 robos exitosos entre todos"},
    "collects": {"name": "💰 Cobradores",         "key": "collect",     "goal": 30,  "reward": 500_000_000,
                 "desc": "Cobren 30 roles con /collect entre todos"},
    "diarias":  {"name": "🎁 Constantes",         "key": "daily_used",  "goal": 20,  "reward": 150_000_000,
                 "desc": "Reclamen 20 recompensas diarias entre todos"},
}

# ----- evento de doble collect
WEEKEND_DOUBLE_COLLECT = True     # sabados y domingos (UTC) los roles pagan doble
COLLECT_EVENT_MULTIPLIER = 2
COLLECT_EVENT_MULTIPLIER_KEY = "collect_event_multiplier"
MANUAL_EVENT_MAX_MULTIPLIER = 50   # tope de los eventos manuales (/evento); el de fin de semana usa COLLECT_EVENT_MULTIPLIER (x2)

# ----- mines
MINES_TILES = 20                  # 4 filas x 5 columnas
MINES_MAX = 10
MINES_PAYOUT_FACTOR = 0.96        # 4% de ventaja de la casa

ALL_WORDS = ("all", "todo", "todos", "max")


# ------------------------------------------------------------------ utilidades
def _fmt_dur(seconds) -> str:
    seconds = max(0, int(seconds))
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    parts = []
    if d:
        parts.append(f"{d}d")
    if h or d:
        parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)


def _bar(current: int, goal: int, width: int = 10) -> str:
    filled = int(width * min(current, goal) / goal) if goal else width
    return "█" * filled + "░" * (width - filled)


def week_key(dt: datetime | None = None) -> str:
    """Lunes (UTC) de la semana de dt, como texto YYYY-MM-DD."""
    dt = dt or datetime.utcnow()
    return (dt - timedelta(days=dt.weekday())).date().isoformat()


def next_week_start(dt: datetime | None = None) -> datetime:
    dt = dt or datetime.utcnow()
    monday = datetime.fromisoformat(week_key(dt))
    return monday + timedelta(days=7)


def parse_amount_or_all(text, available: int) -> int | None:
    t = str(text).strip().lower()
    if t in ALL_WORDS:
        return available
    return loan_parse_amount(t)


def _err_embed(title: str, message: str) -> discord.Embed:
    return discord.Embed(title=f"❌ {title}", description=message, color=0xFF4444)


def _settings_db(scope: str):
    return GLOBAL_DB_PATH if scope == "global" else DB_PATH


async def setting_get(key: str, default: str | None = None, *, scope: str = "guild") -> str | None:
    async with aiosqlite.connect(_settings_db(scope)) as db:
        async with db.execute("SELECT value FROM bot_settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
    return row[0] if row else default


async def setting_set(key: str, value: str, *, scope: str = "guild"):
    async with aiosqlite.connect(_settings_db(scope)) as db:
        await db.execute(
            "INSERT INTO bot_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await db.commit()


async def setting_del(key: str, *, scope: str = "guild"):
    async with aiosqlite.connect(_settings_db(scope)) as db:
        await db.execute("DELETE FROM bot_settings WHERE key=?", (key,))
        await db.commit()


async def init_extras_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        statements = (
            "CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, value TEXT)",
            """CREATE TABLE IF NOT EXISTS jail (
                user_id TEXT PRIMARY KEY, until TEXT NOT NULL,
                strikes INTEGER NOT NULL DEFAULT 1, last_strike TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS user_stats (
                user_id TEXT NOT NULL, stat TEXT NOT NULL, value INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, stat))""",
            """CREATE TABLE IF NOT EXISTS achievements (
                user_id TEXT NOT NULL, key TEXT NOT NULL, unlocked_at TEXT NOT NULL,
                PRIMARY KEY (user_id, key))""",
            """CREATE TABLE IF NOT EXISTS weekly_snapshot (
                week_key TEXT NOT NULL, user_id TEXT NOT NULL, networth INTEGER NOT NULL,
                PRIMARY KEY (week_key, user_id))""",
            """CREATE TABLE IF NOT EXISTS clans (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                owner_id TEXT NOT NULL, bank INTEGER NOT NULL DEFAULT 0,
                open INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS clan_members (
                user_id TEXT PRIMARY KEY, clan_id INTEGER NOT NULL, joined_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS clan_invites (
                clan_id INTEGER NOT NULL, user_id TEXT NOT NULL, PRIMARY KEY (clan_id, user_id))""",
            """CREATE TABLE IF NOT EXISTS clan_missions (
                clan_id INTEGER NOT NULL, week_key TEXT NOT NULL, mission_key TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0, done INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (clan_id, week_key, mission_key))""",
            """CREATE TABLE IF NOT EXISTS custom_items (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL, price INTEGER NOT NULL,
                collect_bonus INTEGER NOT NULL, collect_hours INTEGER NOT NULL, role_id TEXT NOT NULL,
                created_by TEXT, created_at TEXT)""",
            """CREATE TABLE IF NOT EXISTS role_listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id TEXT NOT NULL, item_id TEXT NOT NULL,
                mode TEXT NOT NULL, price INTEGER NOT NULL, days INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, UNIQUE (seller_id, item_id))""",
        )
        for sql in statements:
            await db.execute(sql)
        await db.commit()


# ------------------------------------------------------------------ avisos al usuario
_last_channel: dict = {}   # user_id -> ultimo canal donde uso el bot (para avisar logros)


async def _dm_user(user_id: str, text: str, embed: discord.Embed | None = None):
    try:
        user = client.get_user(int(user_id)) or await client.fetch_user(int(user_id))
        await user.send(text, embed=embed)
    except (discord.HTTPException, ValueError):
        pass  # DMs cerrados o usuario inexistente


async def _notify_user(user_id: str, text: str, embed: discord.Embed | None = None):
    channel = _last_channel.get(user_id)
    if channel is not None:
        try:
            await channel.send(text, embed=embed)
            return
        except (discord.HTTPException, AttributeError):
            pass
    await _dm_user(user_id, text, embed)


# ------------------------------------------------------------------ estadisticas y logros
ACHIEVEMENTS = {
    "primer_millon":  {"name": "💵 Primer millón",        "desc": "Junta 1,000,000 🪙 entre cartera y banco",   "kind": "wealth", "goal": 1_000_000,         "reward": 500_000},
    "mil_millones":   {"name": "💰 Mil millones",         "desc": "Junta 1,000,000,000 🪙",                     "kind": "wealth", "goal": 1_000_000_000,     "reward": 50_000_000},
    "billonario":     {"name": "🏦 Billonario",           "desc": "Junta 1,000,000,000,000 🪙",                 "kind": "wealth", "goal": 1_000_000_000_000, "reward": 500_000_000},
    "primer_robo":    {"name": "🦹 Primer golpe",         "desc": "Consigue tu primer robo exitoso",            "kind": "stat", "stat": "rob_success", "goal": 1,   "reward": 100_000},
    "ladron_10":      {"name": "🥷 Ladrón de guante blanco", "desc": "10 robos exitosos",                       "kind": "stat", "stat": "rob_success", "goal": 10,  "reward": 5_000_000},
    "ladron_50":      {"name": "😈 Maestro del hurto",    "desc": "50 robos exitosos",                          "kind": "stat", "stat": "rob_success", "goal": 50,  "reward": 50_000_000},
    "primera_carcel": {"name": "🔒 Primera celda",        "desc": "Que te atrapen robando por primera vez",     "kind": "stat", "stat": "jailed", "goal": 1,        "reward": 0},
    "reincidente":    {"name": "⛓️ Reincidente",          "desc": "Ve a la cárcel 10 veces",                    "kind": "stat", "stat": "jailed", "goal": 10,       "reward": 1_000_000},
    "cobrador_1":     {"name": "🪙 Primer cobro",         "desc": "Cobra un rol con /collect",                  "kind": "stat", "stat": "collect", "goal": 1,       "reward": 1_000_000},
    "cobrador_25":    {"name": "📈 Cobrador constante",   "desc": "25 cobros de roles",                         "kind": "stat", "stat": "collect", "goal": 25,      "reward": 25_000_000},
    "cobrador_100":   {"name": "🏭 Máquina de dinero",    "desc": "100 cobros de roles",                        "kind": "stat", "stat": "collect", "goal": 100,     "reward": 100_000_000},
    "diario_7":       {"name": "📅 Una semana seguida",   "desc": "Reclama 7 recompensas diarias",              "kind": "stat", "stat": "daily_used", "goal": 7,    "reward": 5_000_000},
    "apostador_100":  {"name": "🎲 Apostador",            "desc": "Juega 100 partidas (slots, ruleta, crash, mines)", "kind": "stat", "stat": "plays", "goal": 100,  "reward": 10_000_000},
    "apostador_1000": {"name": "🎰 Leyenda del casino",   "desc": "Juega 1,000 partidas",                       "kind": "stat", "stat": "plays", "goal": 1000, "reward": 100_000_000},
    "buscaminas_10":  {"name": "💎 Buscador de diamantes","desc": "Retírate con ganancias en mines 10 veces",   "kind": "stat", "stat": "mines_cashout", "goal": 10, "reward": 10_000_000},
    "blackjack_10":   {"name": "🃏 Rey del blackjack",    "desc": "Gana 10 manos de blackjack",                 "kind": "stat", "stat": "blackjack_won", "goal": 10, "reward": 10_000_000},
    "con_rango":      {"name": "👑 Con rango",            "desc": "Ten algún rol de la tienda",                 "kind": "role_any", "goal": 1,                    "reward": 5_000_000},
    "rey_obsidiana":  {"name": "⚫ Rey Obsidiana",        "desc": "Ten el rol Obsidiana",                       "kind": "role", "item": "obsidiana", "goal": 1,   "reward": 250_000_000},
    "generoso":       {"name": "🤝 Generoso",             "desc": "Presta un rol a otro jugador",               "kind": "stat", "stat": "roles_lent", "goal": 1,    "reward": 1_000_000},
    "empresario":     {"name": "🏪 Empresario",           "desc": "Vende o alquila un rol en el mercado",       "kind": "stat", "stat": "roles_market", "goal": 1,  "reward": 5_000_000},
    "clanero":        {"name": "🛡️ Clanero",              "desc": "Únete o crea un clan",                       "kind": "clan", "goal": 1,                        "reward": 1_000_000},
    "luchador":       {"name": "🥊 Luchador",             "desc": "Consigue un luchador",                       "kind": "fighter", "goal": 1,                     "reward": 500_000},
}


async def stat_inc(user_id: str, stat: str, n: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO user_stats (user_id, stat, value) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, stat) DO UPDATE SET value = value + excluded.value",
            (user_id, stat, n),
        )
        await db.commit()


async def _achievement_context(user_id: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT balance + COALESCE(bank, 0) FROM users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        wealth = row[0] if row else 0
        async with db.execute("SELECT stat, value FROM user_stats WHERE user_id=?", (user_id,)) as cur:
            stats = dict(await cur.fetchall())
        async with db.execute(
            "SELECT item_id FROM inventory WHERE user_id=? AND quantity > 0", (user_id,)
        ) as cur:
            roles = {r[0] for r in await cur.fetchall() if r[0] in ROLE_ITEMS}
        async with db.execute("SELECT 1 FROM clan_members WHERE user_id=?", (user_id,)) as cur:
            in_clan = await cur.fetchone() is not None
        async with db.execute("SELECT 1 FROM fighters WHERE user_id=?", (user_id,)) as cur:
            has_fighter = await cur.fetchone() is not None
    return {"wealth": wealth, "stats": stats, "roles": roles, "clan": in_clan, "fighter": has_fighter}


def _achievement_progress(a: dict, ctx: dict) -> tuple[int, int]:
    kind, goal = a["kind"], a["goal"]
    if kind == "wealth":
        return ctx["wealth"], goal
    if kind == "stat":
        return ctx["stats"].get(a["stat"], 0), goal
    if kind == "role_any":
        return (1 if ctx["roles"] else 0), goal
    if kind == "role":
        return (1 if a["item"] in ctx["roles"] else 0), goal
    if kind == "clan":
        return (1 if ctx["clan"] else 0), goal
    if kind == "fighter":
        return (1 if ctx["fighter"] else 0), goal
    return 0, goal


async def achievements_check(user_id: str) -> list[str]:
    """Desbloquea (y paga) los logros que ya cumple. Devuelve los nuevos."""
    ctx = await _achievement_context(user_id)
    new_keys: list[str] = []
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT key FROM achievements WHERE user_id=?", (user_id,)) as cur:
            unlocked = {r[0] for r in await cur.fetchall()}
        for key, a in ACHIEVEMENTS.items():
            if key in unlocked:
                continue
            current, goal = _achievement_progress(a, ctx)
            if current < goal:
                continue
            cur = await db.execute(
                "INSERT OR IGNORE INTO achievements (user_id, key, unlocked_at) VALUES (?, ?, ?)",
                (user_id, key, datetime.utcnow().isoformat()),
            )
            if cur.rowcount == 1:
                new_keys.append(key)
                if a["reward"]:
                    await db.execute(
                        "UPDATE users SET balance = MIN(balance + ?, ?) WHERE user_id=?",
                        (a["reward"], MAX_BALANCE, user_id),
                    )
        await db.commit()
    if new_keys:
        asyncio.create_task(_announce_achievements(user_id, new_keys))
    return new_keys


async def _announce_achievements(user_id: str, keys: list[str]):
    await asyncio.sleep(2)  # que salga despues de la respuesta del comando
    lines = []
    for key in keys:
        a = ACHIEVEMENTS[key]
        reward = f" · **+{a['reward']:,}** 🪙" if a["reward"] else ""
        lines.append(f"{a['name']} — {a['desc']}{reward}")
    await _notify_user(user_id, f"<@{user_id}> 🏅 **¡Logro desbloqueado!**\n" + "\n".join(lines))


_PLAY_ACTIONS = {"slots_played", "roulette_played", "crash_played", "mines_played", "hilo_played"}


async def feature_hook(user_id: str, action: str, n: int = 1):
    """Alimenta logros y misiones de clan. Nunca debe romper un comando."""
    try:
        await stat_inc(user_id, action, n)
        clan_key = action
        if action in _PLAY_ACTIONS:
            await stat_inc(user_id, "plays", n)
            clan_key = "plays"
        await clan_progress(user_id, clan_key, n)
        await achievements_check(user_id)
    except Exception as exc:
        print(f"Error en feature_hook({action}): {exc}")


def build_achievements_embed(name: str, ctx: dict, unlocked: set[str]) -> discord.Embed:
    embed = discord.Embed(title=f"🏅 Logros de {name}", color=0xF1C40F)
    done = [k for k in ACHIEVEMENTS if k in unlocked]
    todo = [k for k in ACHIEVEMENTS if k not in unlocked]
    embed.description = f"Desbloqueados: **{len(done)}/{len(ACHIEVEMENTS)}**"
    if done:
        embed.add_field(
            name="✅ Insignias",
            value="\n".join(f"{ACHIEVEMENTS[k]['name']} — {ACHIEVEMENTS[k]['desc']}" for k in done)[:1024],
            inline=False,
        )
    if todo:
        lines = []
        for k in todo:
            cur, goal = _achievement_progress(ACHIEVEMENTS[k], ctx)
            lines.append(
                f"{ACHIEVEMENTS[k]['name']} — {ACHIEVEMENTS[k]['desc']}\n"
                f"`[{_bar(cur, goal)}]` {min(cur, goal):,}/{goal:,}"
            )
        chunk, size, part = [], 0, 1
        for line in lines:
            if size + len(line) + 2 > 1000:
                embed.add_field(name="🔒 Pendientes" if part == 1 else "🔒 Pendientes (cont.)",
                                value="\n\n".join(chunk), inline=False)
                chunk, size, part = [], 0, part + 1
            chunk.append(line)
            size += len(line) + 2
        if chunk:
            embed.add_field(name="🔒 Pendientes" if part == 1 else "🔒 Pendientes (cont.)",
                            value="\n\n".join(chunk), inline=False)
    return embed


async def logros_embed_for(user_id: str, username: str) -> discord.Embed:
    await get_or_create_user(user_id, username)
    await achievements_check(user_id)
    ctx = await _achievement_context(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT key FROM achievements WHERE user_id=?", (user_id,)) as cur:
            unlocked = {r[0] for r in await cur.fetchall()}
    return build_achievements_embed(username, ctx, unlocked)


@tree.command(name="logros", description="Mira tus insignias y tu progreso (o el de otro jugador)")
@app_commands.describe(usuario="Jugador a consultar (opcional)")
async def logros_command(interaction: discord.Interaction, usuario: _LoanOptional[discord.Member] = None):
    target = usuario or interaction.user
    await interaction.response.defer()
    embed = await logros_embed_for(str(target.id), target.display_name)
    await interaction.followup.send(embed=embed)


# ------------------------------------------------------------------ carcel
async def jail_remaining(user_id: str) -> timedelta | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT until FROM jail WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    try:
        remaining = datetime.fromisoformat(row[0]) - datetime.utcnow()
    except ValueError:
        return None
    return remaining if remaining.total_seconds() > 0 else None


async def jail_send(user_id: str) -> int:
    """Manda al usuario a la carcel. Devuelve los minutos que le tocan."""
    now = datetime.utcnow()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT strikes, last_strike FROM jail WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
        strikes = 1
        if row:
            try:
                if now - datetime.fromisoformat(row[1]) < timedelta(hours=JAIL_STRIKE_RESET_HOURS):
                    strikes = row[0] + 1
            except ValueError:
                pass
        minutes = min(JAIL_BASE_MINUTES + JAIL_EXTRA_MINUTES_PER_STRIKE * (strikes - 1), JAIL_MAX_MINUTES)
        until = now + timedelta(minutes=minutes)
        await db.execute(
            "INSERT INTO jail (user_id, until, strikes, last_strike) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET until=excluded.until, strikes=excluded.strikes, "
            "last_strike=excluded.last_strike",
            (user_id, until.isoformat(), strikes, now.isoformat()),
        )
        await db.commit()
    await feature_hook(user_id, "jailed")
    return minutes


def jail_embed(remaining: timedelta) -> discord.Embed:
    minutes = max(1, _loan_math.ceil(remaining.total_seconds() / 60))
    embed = discord.Embed(title="🔒 Estás en la cárcel", color=0xFF4444)
    embed.description = (
        f"No puedes robar ni jugar apuestas durante **{_fmt_dur(remaining.total_seconds())}**.\n"
        f"💸 Fianza para salir ya: **{minutes * JAIL_BAIL_PER_MINUTE:,}** 🪙 → `/fianza`"
    )
    return embed


async def jail_pay_bail(user_id: str, username: str) -> discord.Embed:
    await get_or_create_user(user_id, username)
    remaining = await jail_remaining(user_id)
    if remaining is None:
        return discord.Embed(title="✅ Estás libre", description="No estás en la cárcel.", color=0x00FF88)
    minutes = max(1, _loan_math.ceil(remaining.total_seconds() / 60))
    cost = minutes * JAIL_BAIL_PER_MINUTE
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (cost, user_id, cost)
        )
        if cur.rowcount == 0:
            await db.rollback()
            balance = await get_balance(user_id)
            return _err_embed("Fianza insuficiente",
                              f"La fianza cuesta **{cost:,}** 🪙 y tienes **{balance:,}** 🪙.")
        await db.execute("UPDATE jail SET until=? WHERE user_id=?", (datetime.utcnow().isoformat(), user_id))
        await db.commit()
    return discord.Embed(title="🔓 Fianza pagada",
                         description=f"Pagaste **{cost:,}** 🪙 y quedaste libre. ¡Pórtate bien!", color=0x00FF88)


async def _jail_interaction_check(interaction: discord.Interaction) -> bool:
    """Se ejecuta antes de cada comando slash: fija el servidor, aplica la blacklist y la cárcel."""
    try:
        uid = str(interaction.user.id)
        _last_channel[uid] = interaction.channel
        is_command = interaction.type is discord.InteractionType.application_command
        name = (interaction.data or {}).get("name")
        if name == "blacklist":
            return True   # es global; el propio comando comprueba que seas el dueño
        if interaction.guild_id is None:
            if is_command and name in ("help", "guía"):
                return True   # no usan la economía
            if is_command:
                await interaction.response.send_message(
                    "❌ La economía es por servidor: usa los comandos dentro de un servidor.", ephemeral=True)
            return False
        try:
            await enter_guild(interaction.guild_id)
        except Exception as exc:
            print(f"Error preparando el servidor {interaction.guild_id}: {exc}")
            if is_command:
                await interaction.response.send_message(
                    "❌ No pude preparar la economía de este servidor. Inténtalo de nuevo.", ephemeral=True)
            return False
        if is_command and name not in BLACKLIST_EXEMPT_COMMANDS:
            blocked = _blacklist_block_for(interaction)
            if blocked:
                await interaction.response.send_message(blocked, ephemeral=True)
                return False
        if is_command and name in JAIL_BLOCKED_COMMANDS:
            remaining = await jail_remaining(uid)
            if remaining is not None:
                await interaction.response.send_message(embed=jail_embed(remaining), ephemeral=True)
                return False
    except Exception as exc:
        print(f"Error en el chequeo previo del comando: {exc}")
    return True

tree.interaction_check = _jail_interaction_check


async def jail_block_prefix(message: discord.Message, cmd: str) -> bool:
    if cmd not in JAIL_BLOCKED_PREFIX:
        return False
    remaining = await jail_remaining(str(message.author.id))
    if remaining is None:
        return False
    await message.channel.send(embed=jail_embed(remaining))
    return True


@tree.command(name="fianza", description="Paga la fianza para salir de la cárcel antes de tiempo")
async def fianza_command(interaction: discord.Interaction):
    embed = await jail_pay_bail(str(interaction.user.id), interaction.user.name)
    await interaction.response.send_message(embed=embed)


@tree.command(name="carcel", description="Mira cuánto te falta en la cárcel (o a otro jugador)")
@app_commands.describe(usuario="Jugador a consultar (opcional)")
async def carcel_command(interaction: discord.Interaction, usuario: _LoanOptional[discord.Member] = None):
    target = usuario or interaction.user
    remaining = await jail_remaining(str(target.id))
    if remaining is None:
        await interaction.response.send_message(f"✅ **{target.display_name}** no está en la cárcel.", ephemeral=True)
    else:
        await interaction.response.send_message(embed=jail_embed(remaining), ephemeral=True)


# ------------------------------------------------------------------ evento: doble collect
def _event_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _configured_collect_multiplier() -> int:
    try:
        return max(1, min(10, int(COLLECT_EVENT_MULTIPLIER)))
    except (TypeError, ValueError):
        return 2


async def _collect_multiplier(db, now: datetime) -> int:
    async with db.execute("SELECT value FROM bot_settings WHERE key='double_collect_until'") as cur:
        row = await cur.fetchone()
    if row:
        until = _event_datetime(row[0])
        if until and now < until:
            async with db.execute(
                "SELECT value FROM bot_settings WHERE key=?", (COLLECT_EVENT_MULTIPLIER_KEY,)
            ) as cur:
                multiplier_row = await cur.fetchone()
            try:
                multiplier = int(multiplier_row[0]) if multiplier_row else _configured_collect_multiplier()
            except (TypeError, ValueError):
                multiplier = _configured_collect_multiplier()
            multiplier = max(1, min(MANUAL_EVENT_MAX_MULTIPLIER, multiplier))
            if WEEKEND_DOUBLE_COLLECT and now.weekday() >= 5:
                multiplier = max(multiplier, _configured_collect_multiplier())   # nunca por debajo del de fin de semana
            return multiplier
    if WEEKEND_DOUBLE_COLLECT and now.weekday() >= 5:
        return _configured_collect_multiplier()
    return 1


async def collect_event_info(now: datetime | None = None) -> tuple[int, str]:
    """(multiplicador actual, texto de estado)."""
    now = now or datetime.utcnow()
    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)
    async with aiosqlite.connect(DB_PATH) as db:
        mult = await _collect_multiplier(db, now)
        async with db.execute("SELECT value FROM bot_settings WHERE key='double_collect_until'") as cur:
            row = await cur.fetchone()
        async with db.execute(
            "SELECT value FROM bot_settings WHERE key=?", (COLLECT_EVENT_MULTIPLIER_KEY,)
        ) as cur:
            multiplier_row = await cur.fetchone()
    lines = []
    if mult > 1:
        lines.append(f"🎉 **¡Evento activo!** Los roles pagan **x{mult}** en `/collect`.")
    else:
        lines.append("😴 No hay ningún evento activo ahora mismo.")
    if row:
        until = _event_datetime(row[0])
        if until and until > now:
            try:
                manual_multiplier = int(multiplier_row[0]) if multiplier_row else _configured_collect_multiplier()
            except (TypeError, ValueError):
                manual_multiplier = _configured_collect_multiplier()
            lines.append(
                f"⏳ Evento manual x{manual_multiplier} termina "
                f"<t:{_loan_ts(until.isoformat())}:R>."
            )
    if WEEKEND_DOUBLE_COLLECT:
        if now.weekday() >= 5:
            end = datetime.fromisoformat(week_key(now)) + timedelta(days=7)
            lines.append(
                f"📅 Fin de semana de collect x{_configured_collect_multiplier()}: "
                f"termina <t:{_loan_ts(end.isoformat())}:R>."
            )
        else:
            start = datetime.fromisoformat(week_key(now)) + timedelta(days=5)
            lines.append(
                f"📅 Próximo fin de semana x{_configured_collect_multiplier()}: "
                f"empieza <t:{_loan_ts(start.isoformat())}:R> (sábado 00:00 UTC)."
            )
    return mult, "\n".join(lines)


async def manual_collect_event_active() -> bool:
    until = _event_datetime(await setting_get("double_collect_until"))
    return until is not None and until > datetime.utcnow()


async def save_manual_collect_event(multiplier: int, until: datetime):
    multiplier = int(multiplier)
    if not 1 <= multiplier <= MANUAL_EVENT_MAX_MULTIPLIER:
        raise ValueError(f"El multiplicador debe estar entre x1 y x{MANUAL_EVENT_MAX_MULTIPLIER}.")
    until = until.astimezone(timezone.utc).replace(tzinfo=None) if until.tzinfo else until
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        for key, value in (
            ("double_collect_until", until.isoformat()),
            (COLLECT_EVENT_MULTIPLIER_KEY, str(multiplier)),
        ):
            await db.execute(
                "INSERT INTO bot_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
        await db.commit()


async def cancel_manual_collect_event() -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute(
            "SELECT value FROM bot_settings WHERE key='double_collect_until'"
        ) as cur:
            row = await cur.fetchone()
        await db.execute(
            "DELETE FROM bot_settings WHERE key IN ('double_collect_until', ?)",
            (COLLECT_EVENT_MULTIPLIER_KEY,),
        )
        await db.commit()
    until = _event_datetime(row[0]) if row else None
    return until is not None and until > datetime.utcnow()


def interaction_is_admin(interaction: discord.Interaction) -> bool:
    permissions = getattr(interaction.user, "guild_permissions", None)
    return bool(permissions and permissions.administrator)


_EVENT_MULTIPLIERS = (2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 25, 30, 35, 40, 45, 50)
_EVENT_DURATIONS = (1, 2, 3, 5, 7, 14, 30, 60, 90, 180, 365)


def _event_multiplier_emoji(multiplier: int) -> str:
    if multiplier <= 3:
        return "⚡"
    if multiplier <= 6:
        return "🔥"
    if multiplier <= 9:
        return "🌟"
    if multiplier <= 15:
        return "💎"
    if multiplier <= 30:
        return "🚀"
    return "🏆" if multiplier >= 50 else "👑"


class CollectEventMultiplierSelect(discord.ui.Select):
    def __init__(self, selected: int = 2):
        super().__init__(
            placeholder="Elige el multiplicador",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=f"Collect x{multiplier} — ganancias x{multiplier} 🪙",
                    value=str(multiplier),
                    emoji=_event_multiplier_emoji(multiplier),
                    default=multiplier == selected,
                )
                for multiplier in _EVENT_MULTIPLIERS
            ],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        view: CollectEventPanelView = self.view
        view.multiplier = int(self.values[0])
        view.sync_defaults()
        await interaction.response.edit_message(embed=view.make_embed(), view=view)


class CollectEventDurationSelect(discord.ui.Select):
    def __init__(self, selected: int = 1):
        super().__init__(
            placeholder="Elige la duración",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=(f"{days} día" if days == 1 else f"{days} días") + f" — {days * 24:,} horas",
                    value=str(days),
                    emoji="🕐" if days <= 3 else ("📅" if days <= 30 else "🗓️"),
                    default=days == selected,
                )
                for days in _EVENT_DURATIONS
            ],
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        view: CollectEventPanelView = self.view
        view.duration_days = int(self.values[0])
        view.sync_defaults()
        await interaction.response.edit_message(embed=view.make_embed(), view=view)


class CollectEventDurationModal(GuildModal, title="Duración personalizada"):
    days = discord.ui.TextInput(
        label="Duración en días (1–365)",
        placeholder="Ejemplo: 12",
        min_length=1,
        max_length=3,
    )

    def __init__(self, parent_view: "CollectEventPanelView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        view = self.parent_view
        if str(interaction.user.id) != view.owner_id or not interaction_is_admin(interaction):
            await interaction.response.send_message(
                "Solo el administrador que abrió el panel puede cambiar estos valores.",
                ephemeral=True,
            )
            return
        try:
            days = int(self.days.value.strip())
        except ValueError:
            await interaction.response.send_message("Escribe un número válido de días.", ephemeral=True)
            return
        if not 1 <= days <= 365:
            await interaction.response.send_message(
                "La duración debe estar entre 1 y 365 días.", ephemeral=True
            )
            return
        view.duration_days = days
        view.sync_defaults()
        if view.message:
            try:
                await view.message.edit(embed=view.make_embed(), view=view)
            except discord.HTTPException:
                await interaction.response.send_message(
                    "No pude actualizar el panel. Vuelve a ejecutar `/evento`.",
                    ephemeral=True,
                )
                return
        await interaction.response.send_message(
            f"✅ Duración fijada en {days} día(s). Pulsa «Activar evento» en el panel.",
            ephemeral=True,
        )


class CollectEventCustomDurationButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Días personalizados",
            emoji="✏️",
            style=discord.ButtonStyle.secondary,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CollectEventDurationModal(self.view))


class CollectEventActivateButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Activar evento",
            emoji="🎉",
            style=discord.ButtonStyle.success,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        view: CollectEventPanelView = self.view
        if view.done:
            await interaction.response.send_message("Este panel ya se usó.", ephemeral=True)
            return
        if await manual_collect_event_active():
            await interaction.response.send_message(
                "Ya hay un evento manual activo. Usa `/cancelar evento` antes de iniciar otro.",
                ephemeral=True,
            )
            return
        until = datetime.utcnow() + timedelta(days=view.duration_days)
        await save_manual_collect_event(view.multiplier, until)
        view.done = True
        embed = discord.Embed(
            title="🎉 Evento de collect activado",
            description=(
                f"Los roles pagan **x{view.multiplier}** durante **{view.duration_days} día(s)**.\n"
                f"Termina <t:{_loan_ts(until.isoformat())}:F> "
                f"(<t:{_loan_ts(until.isoformat())}:R>)."
            ),
            color=0x00FF88,
        )
        await interaction.response.edit_message(embed=embed, view=None)


class CollectEventPanelView(GuildView):
    def __init__(self, owner_id: str, current_status: str = ""):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.multiplier = 2
        self.duration_days = 1
        self.current_status = current_status
        self.done = False
        self.message: discord.InteractionMessage | None = None
        self.add_item(CollectEventMultiplierSelect(self.multiplier))
        self.add_item(CollectEventDurationSelect(self.duration_days))
        self.add_item(CollectEventCustomDurationButton())
        self.add_item(CollectEventActivateButton())

    def sync_defaults(self):
        """Marca en cada menú la opción elegida para que se vea al cerrarlo."""
        for child in self.children:
            if isinstance(child, CollectEventMultiplierSelect):
                for option in child.options:
                    option.default = option.value == str(self.multiplier)
            elif isinstance(child, CollectEventDurationSelect):
                for option in child.options:
                    option.default = option.value == str(self.duration_days)

    def make_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎉 Configurar evento de collect",
            description=(
                f"Elige el multiplicador (hasta **x{MANUAL_EVENT_MAX_MULTIPLIER}**) y la duración. "
                "El evento se aplica a las ganancias de `/collect`."
            ),
            color=0x9B59B6,
        )
        embed.add_field(name="Multiplicador elegido", value=f"**x{self.multiplier}**", inline=True)
        embed.add_field(name="Duración elegida", value=f"**{self.duration_days} día(s)**", inline=True)
        if self.current_status:
            embed.add_field(name="Estado actual", value=self.current_status[:1024], inline=False)
        embed.set_footer(text=f"Hasta x{MANUAL_EVENT_MAX_MULTIPLIER} · Duración: 1 a 365 días · Solo el administrador que abrió el panel puede usarlo")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.owner_id:
            await interaction.response.send_message(
                "Este panel pertenece a otro administrador.", ephemeral=True
            )
            return False
        if not interaction_is_admin(interaction):
            await interaction.response.send_message(
                "Necesitas permiso de Administrador para controlar el evento.", ephemeral=True
            )
            return False
        return True


@tree.command(name="evento", description="Consulta el evento o abre el panel para configurarlo")
async def evento_command(interaction: discord.Interaction):
    mult, text = await collect_event_info()
    if interaction.guild is not None and interaction_is_admin(interaction):
        view = CollectEventPanelView(str(interaction.user.id), text)
        await interaction.response.send_message(
            embed=view.make_embed(),
            view=view,
            ephemeral=True,
        )
        view.message = await interaction.original_response()
        return
    embed = discord.Embed(
        title="🎉 Eventos del casino",
        description=text,
        color=0x00FF88 if mult > 1 else 0x95A5A6,
    )
    await interaction.response.send_message(embed=embed)


cancelar_group = app_commands.Group(
    name="cancelar",
    description="Cancela eventos manuales activos",
    guild_only=True,
)
tree.add_command(cancelar_group)


@cancelar_group.command(name="evento", description="[ADMIN] Termina el evento manual de collect")
@app_commands.default_permissions(administrator=True)
async def cancelar_evento_command(interaction: discord.Interaction):
    if not interaction_is_admin(interaction):
        await interaction.response.send_message(
            "❌ Solo los administradores pueden cancelar el evento.",
            ephemeral=True,
        )
        return
    was_active = await cancel_manual_collect_event()
    if was_active:
        message = (
            "✅ Evento manual de collect cancelado. El evento automático de fin de semana "
            "seguirá activo si corresponde."
        )
    else:
        message = (
            "No había un evento manual activo. El evento automático de fin de semana, "
            "si corresponde, no se cancela con este comando."
        )
    await interaction.response.send_message(message, ephemeral=True)


@tree.command(name="doblecollect", description="[ADMIN] Activa un evento de collect por unas horas (0 = terminar el evento)")
@app_commands.describe(
    horas="Horas que dura el evento (0 para terminarlo)",
    multiplicador=f"Multiplicador del evento (2-{MANUAL_EVENT_MAX_MULTIPLIER}, por defecto 2)",
)
@app_commands.default_permissions(administrator=True)
async def doblecollect_command(
    interaction: discord.Interaction,
    horas: app_commands.Range[int, 0, 168],
    multiplicador: app_commands.Range[int, 2, MANUAL_EVENT_MAX_MULTIPLIER] = 2,
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Solo los administradores pueden usar este comando.", ephemeral=True)
        return
    if horas == 0:
        await cancel_manual_collect_event()
        await interaction.response.send_message("✅ Evento manual de collect doble terminado.")
        return
    until = datetime.utcnow() + timedelta(hours=horas)
    multiplier = multiplicador
    await save_manual_collect_event(multiplier, until)
    await interaction.response.send_message(
        f"🎉 **¡Collect x{multiplier} activado!** Los roles pagan x{multiplier} hasta "
        f"<t:{_loan_ts(until.isoformat())}:f> (<t:{_loan_ts(until.isoformat())}:R>)."
    )


# =====================================================================
#  ROLES: prestar, devolver, mis prestamos y mercado de roles
#  Comandos: /prestar  /devolver  /misprestamos  /rolmercado ...
# =====================================================================
async def init_role_loans_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS role_loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                lender_id TEXT NOT NULL,
                borrower_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (lender_id, item_id),
                UNIQUE (borrower_id, item_id)
            )
            """
        )
        for col, ddl in (
            ("lender_percent", "INTEGER NOT NULL DEFAULT 50"),  # % de cada collect para el dueño
            ("price", "INTEGER NOT NULL DEFAULT 0"),             # >0 = alquiler pagado
            ("earned", "INTEGER NOT NULL DEFAULT 0"),            # lo que el dueño ya cobró
        ):
            try:
                await db.execute(f"ALTER TABLE role_loans ADD COLUMN {col} {ddl}")
            except Exception:
                pass  # la columna ya existe
        await db.commit()


def _role_loan_err(message: str) -> discord.Embed:
    return discord.Embed(title="❌ No se pudo prestar el rol", description=message, color=0xFF4444)


async def _fetch_member(guild: discord.Guild, user_id: str) -> discord.Member | None:
    member = guild.get_member(int(user_id))
    if member is not None:
        return member
    try:
        return await guild.fetch_member(int(user_id))
    except (discord.NotFound, discord.HTTPException):
        return None


async def role_is_committed(user_id: str, item_id: str) -> bool:
    """True si el rol esta prestado a otro o publicado en el mercado de roles."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM role_loans WHERE lender_id=? AND item_id=?", (user_id, item_id)
        ) as cur:
            if await cur.fetchone():
                return True
        async with db.execute(
            "SELECT 1 FROM role_listings WHERE seller_id=? AND item_id=?", (user_id, item_id)
        ) as cur:
            return await cur.fetchone() is not None


async def role_loan_create(
    guild: discord.Guild,
    lender: discord.Member,
    borrower: discord.Member,
    item_id: str,
    days: int,
    *,
    price: int = 0,
    lender_percent: int = ROLE_LOAN_LENDER_PERCENT,
) -> tuple[bool, discord.Embed]:
    """Presta (price=0) o alquila (price>0) un rol. Devuelve (ok, embed)."""
    lender_id, borrower_id = str(lender.id), str(borrower.id)
    if borrower.bot:
        return False, _role_loan_err("No puedes prestarle un rol a un bot.")
    if borrower.id == lender.id:
        return False, _role_loan_err("No puedes prestarte un rol a ti mismo.")
    if item_id not in ROLE_ITEMS:
        return False, _role_loan_err("Ese objeto no es un rol de la tienda.")
    if not 1 <= days <= ROLE_LOAN_MAX_DAYS:
        return False, _role_loan_err(f"Los días deben estar entre **1** y **{ROLE_LOAN_MAX_DAYS}**.")

    await get_or_create_user(lender_id, lender.name)
    await get_or_create_user(borrower_id, borrower.name)
    item = SHOP_ITEMS[item_id]
    now = datetime.utcnow()
    expires = now + timedelta(days=days)
    fee = price * ROLE_MARKET_FEE_PERCENT // 100 if price > 0 else 0

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            async with db.execute(
                "SELECT quantity FROM inventory WHERE user_id=? AND item_id=?", (lender_id, item_id)
            ) as cur:
                row = await cur.fetchone()
            if not row or row[0] <= 0:
                await db.rollback()
                return False, _role_loan_err(f"{lender.mention} no tiene **{item['name']}** en su inventario.")

            async with db.execute(
                "SELECT quantity FROM inventory WHERE user_id=? AND item_id=?", (borrower_id, item_id)
            ) as cur:
                row = await cur.fetchone()
            if row and row[0] > 0:
                await db.rollback()
                return False, _role_loan_err(f"{borrower.mention} ya tiene **{item['name']}**.")

            async with db.execute(
                "SELECT lender_id, expires_at FROM role_loans WHERE item_id=? AND (lender_id=? OR borrower_id=?)",
                (item_id, lender_id, borrower_id),
            ) as cur:
                existing = await cur.fetchone()
            if existing:
                await db.rollback()
                if existing[0] == lender_id:
                    msg = f"**{item['name']}** ya está prestado. Espera a que termine el préstamo."
                else:
                    msg = f"{borrower.mention} ya está usando **{item['name']}** prestado."
                return False, _role_loan_err(msg)

            if price > 0:
                cur = await db.execute(
                    "UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?",
                    (price, borrower_id, price),
                )
                if cur.rowcount == 0:
                    await db.rollback()
                    return False, _role_loan_err(f"No tienes suficientes monedas: el alquiler cuesta **{price:,}** 🪙.")
                await db.execute(
                    "UPDATE users SET balance = MIN(balance + ?, ?) WHERE user_id=?",
                    (price - fee, MAX_BALANCE, lender_id),
                )

            await db.execute(
                "INSERT INTO role_loans (guild_id, lender_id, borrower_id, item_id, expires_at, created_at, "
                "lender_percent, price) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (str(guild.id), lender_id, borrower_id, item_id, expires.isoformat(), now.isoformat(),
                 lender_percent, price),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    # Asigna el rol de Discord; si falla, se cancela todo (y se devuelve el dinero)
    error = None
    try:
        _, already_has_role, error = await grant_shop_role(guild, borrower, item_id)
        if already_has_role and not error:
            error = (
                f"{borrower.mention} ya tiene ese rol de Discord; no puedo prestarlo porque "
                "el bot podría quitárselo cuando termine el préstamo o alquiler."
            )
    except discord.Forbidden:
        error = "No tengo permiso para crear o asignar roles. Necesito **Gestionar roles**."
    except (discord.HTTPException, aiosqlite.Error):
        error = "Discord no pudo asignar el rol. Inténtalo de nuevo."
    if error:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM role_loans WHERE lender_id=? AND item_id=?", (lender_id, item_id))
            if price > 0:
                await db.execute("UPDATE users SET balance = MIN(balance + ?, ?) WHERE user_id=?",
                                 (price, MAX_BALANCE, borrower_id))
                await db.execute("UPDATE users SET balance = MAX(balance - ?, 0) WHERE user_id=?",
                                 (price - fee, lender_id))
            await db.commit()
        return False, _role_loan_err(error)

    bonus = item["collect_bonus"]
    lender_share = bonus * lender_percent // 100
    ts = _loan_ts(expires.isoformat())
    day_word = f"día{'s' if days != 1 else ''}"
    if price > 0:
        embed = discord.Embed(title="🔑 Rol alquilado", color=0x00FF88)
        embed.description = (
            f"{borrower.mention} alquiló **{item['name']}** de {lender.mention} por **{days}** {day_word}.\n\n"
            f"💸 Pagó **{price:,}** 🪙 (comisión del casino: {fee:,}).\n"
            f"💰 Cobra **{bonus:,}** 🪙 cada **{item['collect_hours']}h** con `/collect` y se queda con todo.\n"
            f"⏳ Termina <t:{ts}:R> (<t:{ts}:f>); el bot quitará el rol automáticamente.\n\n"
            f"⚠️ Mientras dure el alquiler, {lender.mention} no puede cobrar ese rol."
        )
        await feature_hook(lender_id, "roles_market")
    else:
        embed = discord.Embed(title="🤝 Rol prestado", color=0x00FF88)
        embed.description = (
            f"{lender.mention} le prestó **{item['name']}** a {borrower.mention} por **{days}** {day_word}.\n\n"
            f"💰 {borrower.mention} cobra **{bonus - lender_share:,}** 🪙 cada **{item['collect_hours']}h** con `/collect`.\n"
            f"🏦 {lender.mention} recibe **{lender_share:,}** 🪙 ({lender_percent}%) de cada collect.\n"
            f"⏳ Termina <t:{ts}:R> (<t:{ts}:f>); el bot quitará el rol automáticamente.\n"
            f"↩️ Cualquiera de los dos puede terminarlo antes con `/devolver`.\n\n"
            f"⚠️ Mientras dure el préstamo, {lender.mention} no puede cobrar ese rol con `/collect`."
        )
        await feature_hook(lender_id, "roles_lent")
    return True, embed


# ------------------------------------------------------------------ quitar el rol / vencimiento
async def _role_loan_dm(user_id: str, text: str):
    await _dm_user(user_id, text)


async def _remove_shop_role(guild_id: str, user_id: str, item_id: str, reason: str) -> bool:
    """Quita el rol de Discord si el usuario ya no tiene el objeto. True = ok o nada que hacer."""
    guild = client.get_guild(int(guild_id))
    if guild is None:
        return True
    if await get_item_quantity(user_id, item_id) > 0:
        return True  # lo compró mientras tanto: se queda con el rol
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT role_id FROM shop_guild_roles WHERE guild_id=? AND item_id=?", (guild_id, item_id)
        ) as cur:
            row = await cur.fetchone()
    role = guild.get_role(int(row[0])) if row else None
    if role is None:
        return True
    try:
        member = guild.get_member(int(user_id)) or await guild.fetch_member(int(user_id))
        if role in member.roles:
            await member.remove_roles(role, reason=reason)
    except discord.NotFound:
        pass  # el usuario ya no está en el servidor
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"No pude quitar el rol {item_id} a {user_id} en {guild_id}: {exc}")
        return False
    return True


async def expire_role_loans():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, guild_id, lender_id, borrower_id, item_id, expires_at FROM role_loans"
        ) as cur:
            rows = await cur.fetchall()

    now = datetime.utcnow()
    for loan_id, guild_id, lender_id, borrower_id, item_id, expires_at in rows:
        try:
            if datetime.fromisoformat(expires_at) > now:
                continue
        except ValueError:
            pass  # fecha corrupta: se limpia igual

        item_name = SHOP_ITEMS.get(item_id, {}).get("name", item_id)
        if not await _remove_shop_role(guild_id, borrower_id, item_id, "Préstamo de rol terminado"):
            continue  # se reintenta en la próxima vuelta

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM role_loans WHERE id=?", (loan_id,))
            await db.commit()

        await _role_loan_dm(borrower_id, f"⏰ Terminó tu préstamo de **{item_name}**; el rol fue retirado.")
        await _role_loan_dm(lender_id, f"✅ Tu **{item_name}** prestado terminó y ya puedes volver a cobrarlo con `/collect`.")


async def role_loan_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            await for_each_guild(expire_role_loans)
        except Exception as exc:  # el bucle nunca debe morir
            print(f"Error en role_loan_loop: {exc}")
        await asyncio.sleep(ROLE_LOAN_CHECK_SECONDS)


async def role_loan_end_early(loan_id: int, actor_id: str) -> tuple[bool, discord.Embed]:
    """Devolver (prestatario) o cancelar (dueño) un prestamo antes de tiempo."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT guild_id, lender_id, borrower_id, item_id, lender_percent, price FROM role_loans WHERE id=?",
            (loan_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return False, _err_embed("Préstamo no encontrado", "Ese préstamo ya terminó o no existe.")
    guild_id, lender_id, borrower_id, item_id, lender_percent, price = row
    if actor_id not in (lender_id, borrower_id):
        return False, _err_embed("No es tuyo", "Solo el dueño o quien tiene el rol prestado puede terminarlo.")
    is_rental = price > 0 and lender_percent == 0
    if is_rental and actor_id == lender_id:
        return False, _err_embed("Rol alquilado", "Ese rol fue alquilado y ya está pagado; solo el inquilino puede devolverlo.")
    if not await _remove_shop_role(guild_id, borrower_id, item_id, "Préstamo de rol terminado antes de tiempo"):
        return False, _err_embed("Discord falló", "No pude quitar el rol en este momento. Inténtalo de nuevo.")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM role_loans WHERE id=?", (loan_id,))
        await db.commit()

    item_name = SHOP_ITEMS.get(item_id, {}).get("name", item_id)
    other_id = borrower_id if actor_id == lender_id else lender_id
    if actor_id == borrower_id:
        text = f"↩️ <@{borrower_id}> devolvió **{item_name}**; ya puedes volver a cobrarlo."
        embed = discord.Embed(title="↩️ Rol devuelto", color=0x3498DB,
                              description=f"Devolviste **{item_name}** antes de tiempo." +
                                          (" (El alquiler no se reembolsa.)" if is_rental else ""))
    else:
        text = f"🛑 <@{lender_id}> canceló el préstamo de **{item_name}**; el rol fue retirado."
        embed = discord.Embed(title="🛑 Préstamo cancelado", color=0x3498DB,
                              description=f"Cancelaste el préstamo de **{item_name}**. Ya puedes cobrarlo de nuevo.")
    await _role_loan_dm(other_id, text)
    return True, embed


# ------------------------------------------------------------------ /prestar
async def prestar_role_autocomplete(interaction: discord.Interaction, current: str):
    t = _plain(current)
    uid = str(interaction.user.id)
    rows = await get_inventory(uid)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT item_id FROM role_loans WHERE lender_id=?", (uid,)) as cur:
            lent = {r[0] for r in await cur.fetchall()}
    choices = []
    for item_id, qty in rows:
        item = SHOP_ITEMS.get(item_id)
        if item is None or item["category"] != "rol" or qty <= 0 or item_id in lent:
            continue
        if t and t not in f"{_plain(item['name'])} {_plain(item_id)}":
            continue
        label = f"{item['name']} — +{item['collect_bonus']:,} cada {item['collect_hours']}h"
        choices.append(app_commands.Choice(name=label[:100], value=item_id))
    return choices[:25]


@tree.command(
    name="prestar",
    description=f"Presta un rol de tu inventario por unos días y recibe {ROLE_LOAN_LENDER_PERCENT}% de sus collects",
)
@app_commands.guild_only()
@app_commands.describe(
    usuario="A quién le prestas el rol",
    rol="Elige el rol de tu inventario que vas a prestar",
    dias=f"Días de préstamo (1-{ROLE_LOAN_MAX_DAYS})",
)
async def prestar_command(
    interaction: discord.Interaction,
    usuario: discord.Member,
    rol: str,
    dias: app_commands.Range[int, 1, ROLE_LOAN_MAX_DAYS],
):
    item_id = resolve_shop_item(rol)
    if item_id is None or item_id not in ROLE_ITEMS:
        await interaction.response.send_message(
            embed=_role_loan_err("No encontré ese rol. Elígelo de la lista que aparece al escribir."),
            ephemeral=True,
        )
        return
    if await role_is_committed(str(interaction.user.id), item_id):
        await interaction.response.send_message(
            embed=_role_loan_err("Ese rol ya está prestado o publicado en el mercado de roles."), ephemeral=True
        )
        return
    await interaction.response.defer()
    ok, embed = await role_loan_create(interaction.guild, interaction.user, usuario, item_id, dias)
    if ok:
        await interaction.followup.send(content=usuario.mention, embed=embed)
    else:
        await interaction.followup.send(embed=embed, ephemeral=True)


prestar_command.autocomplete("rol")(prestar_role_autocomplete)


# ------------------------------------------------------------------ /devolver y /misprestamos
async def loan_choice_autocomplete(interaction: discord.Interaction, current: str):
    uid = str(interaction.user.id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT rl.id, rl.item_id, rl.lender_id, rl.borrower_id, rl.expires_at,
                   COALESCE(lu.username, rl.lender_id), COALESCE(bu.username, rl.borrower_id)
            FROM role_loans rl
            LEFT JOIN users lu ON lu.user_id = rl.lender_id
            LEFT JOIN users bu ON bu.user_id = rl.borrower_id
            WHERE rl.lender_id=? OR rl.borrower_id=?
            ORDER BY rl.expires_at
            """,
            (uid, uid),
        ) as cur:
            rows = await cur.fetchall()
    t = _plain(current)
    now = datetime.utcnow()
    choices = []
    for loan_id, item_id, lender_id, borrower_id, expires_at, lender_name, borrower_name in rows:
        name = SHOP_ITEMS.get(item_id, {}).get("name", item_id)
        try:
            left = _fmt_dur((datetime.fromisoformat(expires_at) - now).total_seconds())
        except ValueError:
            left = "?"
        if lender_id == uid:
            label = f"📤 {name} → prestado a {borrower_name} · {left}"
        else:
            label = f"📥 {name} ← de {lender_name} · {left}"
        if t and t not in _plain(label):
            continue
        choices.append(app_commands.Choice(name=label[:100], value=str(loan_id)))
    return choices[:25]


@tree.command(name="devolver", description="Devuelve un rol que te prestaron o cancela uno que prestaste, antes de tiempo")
@app_commands.describe(prestamo="Elige el préstamo que quieres terminar")
async def devolver_command(interaction: discord.Interaction, prestamo: str):
    if not prestamo.strip().isdigit():
        await interaction.response.send_message(
            embed=_err_embed("Elige un préstamo", "Escoge uno de la lista que aparece al escribir."), ephemeral=True
        )
        return
    await interaction.response.defer()
    ok, embed = await role_loan_end_early(int(prestamo), str(interaction.user.id))
    if ok:
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(embed=embed, ephemeral=True)


devolver_command.autocomplete("prestamo")(loan_choice_autocomplete)


def _loan_projection(item_id: str, expires_iso: str, last_collect_iso: str | None,
                     pct: int, now: datetime, mult: int) -> tuple[datetime, int, int]:
    """(proximo collect posible, collects que aun caben, lo que gana el dueño por collect)."""
    item = SHOP_ITEMS[item_id]
    cooldown = timedelta(hours=item["collect_hours"])
    expires = datetime.fromisoformat(expires_iso)
    next_collect = datetime.fromisoformat(last_collect_iso) + cooldown if last_collect_iso else now
    if next_collect < now:
        next_collect = now
    remaining = 0 if next_collect >= expires else 1 + int((expires - next_collect) / cooldown)
    return next_collect, remaining, item["collect_bonus"] * mult * pct // 100


async def build_misprestamos_embed(user_id: str) -> discord.Embed:
    now = datetime.utcnow()
    async with aiosqlite.connect(DB_PATH) as db:
        mult = await _collect_multiplier(db, now)
        async with db.execute(
            """
            SELECT rl.item_id, rl.expires_at, rl.lender_percent, rl.price, rl.earned,
                   COALESCE(u.username, rl.borrower_id), rc.last_collect
            FROM role_loans rl
            LEFT JOIN users u ON u.user_id = rl.borrower_id
            LEFT JOIN role_collects rc ON rc.user_id = rl.borrower_id AND rc.item_id = rl.item_id
            WHERE rl.lender_id=? ORDER BY rl.expires_at
            """,
            (user_id,),
        ) as cur:
            lent = await cur.fetchall()
        async with db.execute(
            """
            SELECT rl.item_id, rl.expires_at, rl.lender_percent, rl.price,
                   COALESCE(u.username, rl.lender_id), rc.last_collect
            FROM role_loans rl
            LEFT JOIN users u ON u.user_id = rl.lender_id
            LEFT JOIN role_collects rc ON rc.user_id = rl.borrower_id AND rc.item_id = rl.item_id
            WHERE rl.borrower_id=? ORDER BY rl.expires_at
            """,
            (user_id,),
        ) as cur:
            borrowed = await cur.fetchall()
        async with db.execute(
            "SELECT id, item_id, mode, price, days FROM role_listings WHERE seller_id=?", (user_id,)
        ) as cur:
            listings = await cur.fetchall()

    embed = discord.Embed(title="📒 Mis préstamos de roles", color=0x3498DB)
    if not lent and not borrowed and not listings:
        embed.description = "No tienes roles prestados, alquilados ni publicados. Usa `/prestar` o `/rolmercado publicar`."
        return embed

    if lent:
        lines, total_pending, total_earned = [], 0, 0
        for item_id, expires_at, pct, price, earned, borrower_name, last_collect in lent:
            name = SHOP_ITEMS.get(item_id, {}).get("name", item_id)
            ts = _loan_ts(expires_at)
            if price > 0 and pct == 0:
                lines.append(f"{name} → **{borrower_name}** · alquilado por **{price:,}** 🪙 (ya cobrado) · termina <t:{ts}:R>")
                continue
            next_collect, remaining, share = _loan_projection(item_id, expires_at, last_collect, pct, now, mult)
            pending = remaining * share
            total_pending += pending
            total_earned += earned
            lines.append(
                f"{name} → **{borrower_name}** · termina <t:{ts}:R>\n"
                f"   💰 Cobrado: **{earned:,}** 🪙 · Falta por cobrar: hasta **{pending:,}** 🪙 "
                f"({remaining} collect{'s' if remaining != 1 else ''} × {share:,})"
                + (f"\n   ⏱️ Próximo collect posible: <t:{_loan_ts(next_collect.isoformat())}:R>" if remaining else "")
            )
        embed.add_field(name="📤 Roles que prestaste", value="\n".join(lines)[:1024], inline=False)
        embed.add_field(name="Totales de préstamos", inline=False,
                        value=f"Ya cobrado: **{total_earned:,}** 🪙 · Pendiente máximo: **{total_pending:,}** 🪙")
    if borrowed:
        lines = []
        for item_id, expires_at, pct, price, lender_name, last_collect in borrowed:
            name = SHOP_ITEMS.get(item_id, {}).get("name", item_id)
            ts = _loan_ts(expires_at)
            item = SHOP_ITEMS.get(item_id)
            mine = item["collect_bonus"] * mult * (100 - pct) // 100 if item else 0
            kind = "alquilado" if price > 0 and pct == 0 else f"prestado ({pct}% para su dueño)"
            lines.append(f"{name} ← **{lender_name}** · {kind}\n   💰 Ganas **{mine:,}** 🪙 por collect · termina <t:{ts}:R>")
        embed.add_field(name="📥 Roles que tienes prestados", value="\n".join(lines)[:1024], inline=False)
    if listings:
        lines = []
        for lid, item_id, mode, price, days in listings:
            name = SHOP_ITEMS.get(item_id, {}).get("name", item_id)
            extra = f" · {days} día(s)" if mode == "alquiler" else ""
            lines.append(f"`#{lid}` {name} · {mode}{extra} · **{price:,}** 🪙")
        embed.add_field(name="🏪 Tus anuncios en el mercado", value="\n".join(lines)[:1024], inline=False)
    if mult > 1:
        embed.set_footer(text=f"Cálculos con el evento collect x{mult} activo")
    return embed


@tree.command(name="misprestamos", description="Mira qué roles prestaste, cuánto has cobrado y cuánto te falta por cobrar")
async def misprestamos_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    embed = await build_misprestamos_embed(str(interaction.user.id))
    await interaction.followup.send(embed=embed, ephemeral=True)


# ------------------------------------------------------------------ mercado de roles
rolmercado_group = app_commands.Group(
    name="rolmercado", description="Compra, vende o alquila roles de la tienda a otros jugadores", guild_only=True
)
tree.add_command(rolmercado_group)


async def role_market_publish(seller: discord.Member, item_id: str, mode: str, price: int, days: int) -> tuple[bool, discord.Embed]:
    seller_id = str(seller.id)
    if item_id not in ROLE_ITEMS:
        return False, _err_embed("Rol no válido", "Elige un rol de la lista.")
    if mode not in ("venta", "alquiler"):
        return False, _err_embed("Modo no válido", "Elige **venta** o **alquiler**.")
    if price <= 0:
        return False, _err_embed("Precio no válido", "El precio debe ser mayor a 0.")
    if mode == "alquiler" and not 1 <= days <= ROLE_LOAN_MAX_DAYS:
        return False, _err_embed("Días no válidos", f"El alquiler debe ser de **1** a **{ROLE_LOAN_MAX_DAYS}** días.")
    await get_or_create_user(seller_id, seller.name)
    item = SHOP_ITEMS[item_id]
    if await get_item_quantity(seller_id, item_id) <= 0:
        return False, _err_embed("Sin rol", f"No tienes **{item['name']}** en tu inventario.")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT 1 FROM role_loans WHERE lender_id=? AND item_id=?", (seller_id, item_id)) as cur:
            lent = await cur.fetchone()
        async with db.execute("SELECT id FROM role_listings WHERE seller_id=? AND item_id=?", (seller_id, item_id)) as cur:
            listed = await cur.fetchone()
        if lent or listed:
            await db.rollback()
            return False, _err_embed("No disponible", "Ese rol ya está prestado o publicado en el mercado.")
        cur = await db.execute(
            "INSERT INTO role_listings (seller_id, item_id, mode, price, days, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (seller_id, item_id, mode, price, days if mode == "alquiler" else 0, datetime.utcnow().isoformat()),
        )
        listing_id = cur.lastrowid
        await db.commit()
    fee_note = f"Comisión del casino: **{ROLE_MARKET_FEE_PERCENT}%** (recibirás {price - price * ROLE_MARKET_FEE_PERCENT // 100:,} 🪙)."
    if mode == "venta":
        what = f"🛒 **Venta** por **{price:,}** 🪙 — el rol pasa al comprador."
    else:
        what = f"🔑 **Alquiler** por **{price:,}** 🪙 durante **{days}** día(s) — el inquilino cobra el 100% de los collects."
    embed = discord.Embed(title="🏪 Anuncio publicado", color=0x00FF88,
                          description=f"`#{listing_id}` {item['name']}\n{what}\n{fee_note}\n\nRetíralo con `/rolmercado retirar`.")
    return True, embed


def _listing_line(lid, item_id, mode, price, days, seller_name) -> str:
    item = SHOP_ITEMS.get(item_id, {"name": item_id, "collect_bonus": 0, "collect_hours": 0})
    if mode == "venta":
        what = f"🛒 Venta · **{price:,}** 🪙"
    else:
        what = f"🔑 Alquiler {days}d · **{price:,}** 🪙"
    return (f"`#{lid}` {item['name']} — {what}\n"
            f"   +{item['collect_bonus']:,} cada {item['collect_hours']}h · vendedor: **{seller_name}**")


async def build_rolmercado_embed(mode: str | None = None) -> discord.Embed:
    async with aiosqlite.connect(DB_PATH) as db:
        sql = ("SELECT rl.id, rl.item_id, rl.mode, rl.price, rl.days, COALESCE(u.username, rl.seller_id) "
               "FROM role_listings rl LEFT JOIN users u ON u.user_id = rl.seller_id ")
        params: tuple = ()
        if mode in ("venta", "alquiler"):
            sql += "WHERE rl.mode=? "
            params = (mode,)
        sql += "ORDER BY rl.id DESC LIMIT 20"
        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
    embed = discord.Embed(title="🏪 Mercado de roles", color=0x9B59B6)
    if not rows:
        embed.description = "No hay anuncios todavía. Publica uno con `/rolmercado publicar`."
        return embed
    lines = [_listing_line(*r) for r in rows]
    desc, size = [], 0
    for line in lines:
        if size + len(line) + 2 > 3800:
            break
        desc.append(line)
        size += len(line) + 2
    embed.description = "\n\n".join(desc)
    embed.set_footer(text=f"Compra o alquila con /rolmercado comprar · comisión del {ROLE_MARKET_FEE_PERCENT}% al vendedor")
    return embed


async def role_market_buy(guild: discord.Guild, buyer: discord.Member, listing_id: int) -> tuple[bool, discord.Embed]:
    buyer_id = str(buyer.id)
    await get_or_create_user(buyer_id, buyer.name)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT seller_id, item_id, mode, price, days FROM role_listings WHERE id=?", (listing_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return False, _err_embed("Anuncio no encontrado", "Ese anuncio ya no existe.")
    seller_id, item_id, mode, price, days = row
    if seller_id == buyer_id:
        return False, _err_embed("Es tu anuncio", "No puedes comprarte a ti mismo. Usa `/rolmercado retirar`.")
    item = SHOP_ITEMS.get(item_id)
    if item is None:
        return False, _err_embed("Anuncio roto", "Ese rol ya no existe en la tienda.")

    if mode == "alquiler":
        seller = await _fetch_member(guild, seller_id)
        if seller is None:
            return False, _err_embed("Vendedor ausente", "El dueño del rol no está en este servidor.")
        ok, embed = await role_loan_create(guild, seller, buyer, item_id, days, price=price, lender_percent=0)
        if ok:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("DELETE FROM role_listings WHERE id=?", (listing_id,))
                await db.commit()
        return ok, embed

    # ---- venta: el rol cambia de dueño
    fee = price * ROLE_MARKET_FEE_PERCENT // 100
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            async with db.execute("SELECT 1 FROM role_listings WHERE id=?", (listing_id,)) as cur:
                if not await cur.fetchone():
                    await db.rollback()
                    return False, _err_embed("Anuncio no encontrado", "Alguien se te adelantó: ese anuncio ya no existe.")
            async with db.execute(
                "SELECT quantity FROM inventory WHERE user_id=? AND item_id=?", (seller_id, item_id)
            ) as cur:
                srow = await cur.fetchone()
            if not srow or srow[0] <= 0:
                await db.execute("DELETE FROM role_listings WHERE id=?", (listing_id,))
                await db.commit()
                return False, _err_embed("Ya no disponible", "El vendedor ya no tiene ese rol; el anuncio fue eliminado.")
            async with db.execute(
                "SELECT 1 FROM role_loans WHERE lender_id=? AND item_id=?", (seller_id, item_id)
            ) as cur:
                if await cur.fetchone():
                    await db.rollback()
                    return False, _err_embed("Rol prestado", "Ese rol está prestado ahora mismo; inténtalo más tarde.")
            async with db.execute(
                "SELECT quantity FROM inventory WHERE user_id=? AND item_id=?", (buyer_id, item_id)
            ) as cur:
                brow = await cur.fetchone()
            async with db.execute(
                "SELECT 1 FROM role_loans WHERE borrower_id=? AND item_id=?", (buyer_id, item_id)
            ) as cur:
                borrowing = await cur.fetchone()
            if (brow and brow[0] > 0) or borrowing:
                await db.rollback()
                return False, _err_embed("Ya lo tienes", f"Ya tienes **{item['name']}** (propio o prestado).")

            cur = await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (price, buyer_id, price)
            )
            if cur.rowcount == 0:
                await db.rollback()
                balance = await get_balance(buyer_id)
                return False, _err_embed("Saldo insuficiente", f"Cuesta **{price:,}** 🪙 y tienes **{balance:,}** 🪙.")
            await db.execute("UPDATE users SET balance = MIN(balance + ?, ?) WHERE user_id=?",
                             (price - fee, MAX_BALANCE, seller_id))
            await db.execute("UPDATE inventory SET quantity = quantity - 1 WHERE user_id=? AND item_id=?",
                             (seller_id, item_id))
            await db.execute("DELETE FROM inventory WHERE user_id=? AND item_id=? AND quantity <= 0",
                             (seller_id, item_id))
            await db.execute(
                "INSERT INTO inventory (user_id, item_id, quantity) VALUES (?, ?, 1) "
                "ON CONFLICT(user_id, item_id) DO UPDATE SET quantity = quantity + 1",
                (buyer_id, item_id),
            )
            # el comprador hereda el cooldown del collect (si no, cobraria dos veces en el mismo ciclo)
            async with db.execute(
                "SELECT last_collect FROM role_collects WHERE user_id=? AND item_id=?", (seller_id, item_id)
            ) as cur:
                crow = await cur.fetchone()
            if crow:
                await db.execute(
                    "INSERT INTO role_collects (user_id, item_id, last_collect) VALUES (?, ?, ?) "
                    "ON CONFLICT(user_id, item_id) DO UPDATE SET "
                    "last_collect = MAX(role_collects.last_collect, excluded.last_collect)",
                    (buyer_id, item_id, crow[0]),
                )
            await db.execute("DELETE FROM role_listings WHERE id=?", (listing_id,))
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    # roles de Discord (si falla algo, el comprador puede usar /use)
    note = ""
    try:
        _, _, error = await grant_shop_role(guild, buyer, item_id)
        if error:
            note = f"\n⚠️ {error} Usa `/use` para reclamar el rol de Discord."
    except (discord.HTTPException, aiosqlite.Error):
        note = "\n⚠️ No pude asignar el rol de Discord; usa `/use` para reclamarlo."
    await _remove_shop_role(str(guild.id), seller_id, item_id, "Rol vendido en el mercado de roles")
    await feature_hook(seller_id, "roles_market")

    embed = discord.Embed(title="🛒 ¡Rol comprado!", color=0x00FF88)
    embed.description = (
        f"{buyer.mention} compró **{item['name']}** por **{price:,}** 🪙 a <@{seller_id}>.\n"
        f"💰 El vendedor recibió **{price - fee:,}** 🪙 (comisión {fee:,}).\n"
        f"Ya puedes cobrarlo con `/collect`.{note}"
    )
    return True, embed


async def listing_autocomplete(interaction: discord.Interaction, current: str):
    t = _plain(current)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT rl.id, rl.item_id, rl.mode, rl.price, rl.days, COALESCE(u.username, rl.seller_id) "
            "FROM role_listings rl LEFT JOIN users u ON u.user_id = rl.seller_id "
            "WHERE rl.seller_id != ? ORDER BY rl.id DESC LIMIT 50",
            (str(interaction.user.id),),
        ) as cur:
            rows = await cur.fetchall()
    choices = []
    for lid, item_id, mode, price, days, seller in rows:
        name = SHOP_ITEMS.get(item_id, {}).get("name", item_id)
        what = "Venta" if mode == "venta" else f"Alquiler {days}d"
        label = f"#{lid} {name} · {what} · {price:,} 🪙 · {seller}"
        if t and t not in _plain(label):
            continue
        choices.append(app_commands.Choice(name=label[:100], value=str(lid)))
    return choices[:25]


async def my_listing_autocomplete(interaction: discord.Interaction, current: str):
    t = _plain(current)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, item_id, mode, price, days FROM role_listings WHERE seller_id=? ORDER BY id DESC",
            (str(interaction.user.id),),
        ) as cur:
            rows = await cur.fetchall()
    choices = []
    for lid, item_id, mode, price, days in rows:
        name = SHOP_ITEMS.get(item_id, {}).get("name", item_id)
        what = "Venta" if mode == "venta" else f"Alquiler {days}d"
        label = f"#{lid} {name} · {what} · {price:,} 🪙"
        if t and t not in _plain(label):
            continue
        choices.append(app_commands.Choice(name=label[:100], value=str(lid)))
    return choices[:25]


@rolmercado_group.command(name="publicar", description="Pon un rol de tu inventario en venta o en alquiler")
@app_commands.describe(
    rol="Rol de tu inventario",
    modo="Venta (el rol cambia de dueño) o alquiler (por días)",
    precio="Precio en monedas (acepta 5m, 500k...)",
    dias="Solo alquiler: días que dura (1-30)",
)
@app_commands.choices(modo=[
    app_commands.Choice(name="Venta (el rol pasa al comprador)", value="venta"),
    app_commands.Choice(name="Alquiler (por días)", value="alquiler"),
])
async def rolmercado_publicar(
    interaction: discord.Interaction,
    rol: str,
    modo: str,
    precio: str,
    dias: app_commands.Range[int, 1, ROLE_LOAN_MAX_DAYS] = 3,
):
    item_id = resolve_shop_item(rol)
    amount = loan_parse_amount(precio)
    if item_id is None or item_id not in ROLE_ITEMS:
        await interaction.response.send_message(embed=_err_embed("Rol no válido", "Elígelo de la lista."), ephemeral=True)
        return
    if amount is None or amount <= 0:
        await interaction.response.send_message(
            embed=_err_embed("Precio no válido", "Escribe un número, por ejemplo `50000000`, `50m` o `500k`."), ephemeral=True)
        return
    ok, embed = await role_market_publish(interaction.user, item_id, modo, amount, dias)
    await interaction.response.send_message(embed=embed, ephemeral=not ok)


rolmercado_publicar.autocomplete("rol")(prestar_role_autocomplete)


@rolmercado_group.command(name="ver", description="Mira los roles en venta y en alquiler")
@app_commands.describe(modo="Filtrar por venta o alquiler (opcional)")
@app_commands.choices(modo=[
    app_commands.Choice(name="Solo ventas", value="venta"),
    app_commands.Choice(name="Solo alquileres", value="alquiler"),
])
async def rolmercado_ver(interaction: discord.Interaction, modo: _LoanOptional[str] = None):
    await interaction.response.send_message(embed=await build_rolmercado_embed(modo))


@rolmercado_group.command(name="comprar", description="Compra o alquila un rol del mercado")
@app_commands.describe(anuncio="Elige el anuncio")
async def rolmercado_comprar(interaction: discord.Interaction, anuncio: str):
    if not anuncio.strip().lstrip("#").isdigit():
        await interaction.response.send_message(
            embed=_err_embed("Elige un anuncio", "Escoge uno de la lista que aparece al escribir."), ephemeral=True)
        return
    await interaction.response.defer()
    ok, embed = await role_market_buy(interaction.guild, interaction.user, int(anuncio.strip().lstrip("#")))
    if ok:
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(embed=embed, ephemeral=True)


rolmercado_comprar.autocomplete("anuncio")(listing_autocomplete)


@rolmercado_group.command(name="retirar", description="Retira uno de tus anuncios del mercado de roles")
@app_commands.describe(anuncio="Elige tu anuncio")
async def rolmercado_retirar(interaction: discord.Interaction, anuncio: str):
    if not anuncio.strip().lstrip("#").isdigit():
        await interaction.response.send_message(
            embed=_err_embed("Elige un anuncio", "Escoge uno de la lista que aparece al escribir."), ephemeral=True)
        return
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM role_listings WHERE id=? AND seller_id=?",
            (int(anuncio.strip().lstrip("#")), str(interaction.user.id)),
        )
        await db.commit()
    if cur.rowcount == 0:
        await interaction.response.send_message(
            embed=_err_embed("No encontrado", "Ese anuncio no existe o no es tuyo."), ephemeral=True)
    else:
        await interaction.response.send_message("✅ Anuncio retirado del mercado.", ephemeral=True)


rolmercado_retirar.autocomplete("anuncio")(my_listing_autocomplete)


# ------------------------------------------------------------------ prefijo: ,prestar
async def role_loan_handle_prefix(message: discord.Message, cmd: str, args: list) -> bool:
    """Devuelve True si el comando era ,prestar (así el bot no sigue buscando)."""
    if cmd != "prestar":
        return False
    usage = "❌ Uso: `,prestar @usuario <rol> <días>` — ej: `,prestar @Juan oro 3`"
    if message.guild is None or not message.mentions or len(args) < 3 or not args[-1].isdigit():
        await message.channel.send(usage)
        return True
    borrower = message.mentions[0]
    if not isinstance(borrower, discord.Member) or not isinstance(message.author, discord.Member):
        await message.channel.send(usage)
        return True
    name = " ".join(a for a in args[:-1] if not re.fullmatch(r"<@!?\d+>", a))
    item_id = resolve_shop_item(name)
    if item_id is None or item_id not in ROLE_ITEMS:
        await message.channel.send(f"❌ No encontré el rol **{name}**.\n{usage}")
        return True
    if await role_is_committed(str(message.author.id), item_id):
        await message.channel.send(embed=_role_loan_err("Ese rol ya está prestado o publicado en el mercado de roles."))
        return True
    ok, embed = await role_loan_create(message.guild, message.author, borrower, item_id, int(args[-1]))
    await message.channel.send(content=borrower.mention if ok else None, embed=embed)
    return True


# =====================================================================
#  RANKING SEMANAL (/top)  ·  premios automaticos a los 3 primeros
#  Mide cuanto crecio tu patrimonio en la semana: cartera + banco
#  + objetos de la tienda (a mitad de precio) - deuda del banco.
# =====================================================================
async def compute_networths() -> dict[str, tuple[str, int]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT u.user_id, u.username, u.balance, COALESCE(u.bank, 0), COALESCE(l.remaining, 0) "
            "FROM users u LEFT JOIN loans l ON l.user_id = u.user_id"
        ) as cur:
            rows = await cur.fetchall()
        async with db.execute("SELECT user_id, item_id, quantity FROM inventory WHERE quantity > 0") as cur:
            inventory = await cur.fetchall()
    items_value: dict[str, int] = {}
    for user_id, item_id, qty in inventory:
        item = SHOP_ITEMS.get(item_id)
        if item:
            items_value[user_id] = items_value.get(user_id, 0) + qty * (item["price"] // 2)
    return {
        uid: (name or uid, balance + bank - debt + items_value.get(uid, 0))
        for uid, name, balance, bank, debt in rows
    }


async def weekly_snapshot_ensure(wk: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM weekly_snapshot WHERE week_key=? LIMIT 1", (wk,)) as cur:
            if await cur.fetchone():
                return
    worths = await compute_networths()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            "INSERT OR IGNORE INTO weekly_snapshot (week_key, user_id, networth) VALUES (?, ?, ?)",
            [(wk, uid, worth) for uid, (_, worth) in worths.items()],
        )
        await db.execute("DELETE FROM weekly_snapshot WHERE week_key < ?",
                         ((datetime.fromisoformat(wk) - timedelta(days=21)).date().isoformat(),))
        await db.commit()


async def weekly_standings(wk: str) -> list[tuple[str, str, int]]:
    """[(user_id, nombre, ganancia)] de mayor a menor para la semana wk."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, networth FROM weekly_snapshot WHERE week_key=?", (wk,)) as cur:
            base = dict(await cur.fetchall())
    if not base:
        return []
    worths = await compute_networths()
    out = [(uid, name, worth - base.get(uid, 1000)) for uid, (name, worth) in worths.items()]
    out.sort(key=lambda x: x[2], reverse=True)
    return out


async def build_top_embed(viewer_id: str | None = None) -> discord.Embed:
    wk = week_key()
    await weekly_snapshot_ensure(wk)
    standings = await weekly_standings(wk)
    medals = ["🥇", "🥈", "🥉"]
    embed = discord.Embed(title="🏆 Top semanal — ganancias", color=0xFFD700)
    end = next_week_start()
    lines = []
    for i, (uid, name, gain) in enumerate(standings[:10]):
        if gain <= 0:
            break
        prefix = medals[i] if i < 3 else f"**#{i + 1}**"
        lines.append(f"{prefix} **{name}** — {'+' if gain > 0 else ''}{gain:,} 🪙")
    embed.description = "\n".join(lines) if lines else "Nadie ha ganado monedas esta semana todavía. ¡Sé el primero!"
    embed.add_field(
        name="🎁 Premios automáticos",
        value="\n".join(f"{medals[i]} {p:,} 🪙" for i, p in enumerate(WEEKLY_PRIZES)),
        inline=True,
    )
    embed.add_field(name="⏳ Se reinicia", value=f"<t:{_loan_ts(end.isoformat())}:R>\n(lunes 00:00 UTC)", inline=True)
    if viewer_id:
        for i, (uid, name, gain) in enumerate(standings):
            if uid == viewer_id:
                embed.set_footer(text=f"Tu posición: #{i + 1} · {gain:+,} 🪙 esta semana")
                break
    return embed


async def weekly_rollover_check():
    cur_week = week_key()
    last = await setting_get("weekly_week")
    if last is None:
        await setting_set("weekly_week", cur_week)
        await weekly_snapshot_ensure(cur_week)
        return
    if last == cur_week:
        await weekly_snapshot_ensure(cur_week)
        return
    # La semana `last` termino: se paga y se abre la nueva
    standings = await weekly_standings(last)
    winners = [(uid, name, gain) for uid, name, gain in standings[:len(WEEKLY_PRIZES)] if gain > 0]
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (uid, name, gain) in enumerate(winners):
        prize = WEEKLY_PRIZES[i]
        await update_balance(uid, prize)
        lines.append(f"{medals[i]} <@{uid}> — {gain:+,} 🪙 en la semana · premio **{prize:,}** 🪙")
        await _dm_user(uid, f"🏆 ¡Quedaste en el puesto #{i + 1} del top semanal! Ganaste **{prize:,}** 🪙.")
    await setting_set("weekly_week", cur_week)
    await weekly_snapshot_ensure(cur_week)
    if not lines:
        return
    embed = discord.Embed(title="🏆 ¡Terminó el top semanal!", description="\n".join(lines), color=0xFFD700)
    channel_id = await setting_get("top_channel")
    if channel_id:
        channel = client.get_channel(int(channel_id))
        if channel is not None:
            try:
                await channel.send(embed=embed)
            except discord.HTTPException as exc:
                print(f"No pude anunciar el top semanal: {exc}")


async def weekly_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            await for_each_guild(weekly_rollover_check)
        except Exception as exc:  # el bucle nunca debe morir
            print(f"Error en weekly_loop: {exc}")
        await asyncio.sleep(WEEKLY_CHECK_SECONDS)


@tree.command(name="top", description="Ranking semanal de ganancias con premios automáticos para los 3 primeros")
async def top_command(interaction: discord.Interaction):
    await interaction.response.defer()
    embed = await build_top_embed(str(interaction.user.id))
    await interaction.followup.send(embed=embed)


@tree.command(name="topcanal", description="[ADMIN] Elige el canal donde se anuncian los ganadores del top semanal")
@app_commands.describe(canal="Canal de anuncios (por defecto, este canal)")
@app_commands.default_permissions(administrator=True)
async def topcanal_command(interaction: discord.Interaction, canal: _LoanOptional[discord.TextChannel] = None):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Solo los administradores pueden usar este comando.", ephemeral=True)
        return
    target = canal or interaction.channel
    await setting_set("top_channel", str(target.id))
    await interaction.response.send_message(f"✅ Los ganadores del top semanal se anunciarán en {target.mention}.")


# =====================================================================
#  CLANES  ·  banco compartido y misiones semanales en grupo
# =====================================================================
async def clan_of(user_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT c.id, c.name, c.owner_id, c.bank, c.open FROM clan_members m "
            "JOIN clans c ON c.id = m.clan_id WHERE m.user_id=?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return {"id": row[0], "name": row[1], "owner_id": row[2], "bank": row[3], "open": bool(row[4])}


async def clan_by_name(name: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, name, owner_id, bank, open FROM clans WHERE name = ? COLLATE NOCASE", (name.strip(),)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return {"id": row[0], "name": row[1], "owner_id": row[2], "bank": row[3], "open": bool(row[4])}


async def clan_member_ids(clan_id: int) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM clan_members WHERE clan_id=? ORDER BY joined_at, user_id", (clan_id,)
        ) as cur:
            return [r[0] for r in await cur.fetchall()]


async def clan_progress(user_id: str, key: str, n: int = 1):
    """Suma progreso a las misiones semanales del clan del usuario."""
    if not any(m["key"] == key for m in CLAN_MISSIONS.values()):
        return
    clan = await clan_of(user_id)
    if not clan:
        return
    wk = week_key()
    completed: list[dict] = []
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        for mkey, mission in CLAN_MISSIONS.items():
            if mission["key"] != key:
                continue
            async with db.execute(
                "SELECT progress, done FROM clan_missions WHERE clan_id=? AND week_key=? AND mission_key=?",
                (clan["id"], wk, mkey),
            ) as cur:
                row = await cur.fetchone()
            progress, done = row if row else (0, 0)
            if done:
                continue
            new_progress = min(progress + n, mission["goal"])
            finished = new_progress >= mission["goal"]
            await db.execute(
                "INSERT INTO clan_missions (clan_id, week_key, mission_key, progress, done) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(clan_id, week_key, mission_key) DO UPDATE SET progress=excluded.progress, done=excluded.done",
                (clan["id"], wk, mkey, new_progress, 1 if finished else 0),
            )
            if finished:
                await db.execute("UPDATE clans SET bank = MIN(bank + ?, ?) WHERE id=?",
                                 (mission["reward"], MAX_BALANCE, clan["id"]))
                completed.append(mission)
        await db.commit()
    for mission in completed:
        asyncio.create_task(_notify_user(
            user_id,
            f"🎉 ¡El clan **{clan['name']}** completó la misión **{mission['name']}**! "
            f"**+{mission['reward']:,}** 🪙 al banco del clan.",
        ))


async def clan_create(user_id: str, username: str, name: str) -> tuple[bool, str]:
    name = name.strip()
    if not CLAN_NAME_RE.fullmatch(name):
        return False, "El nombre debe tener **3 a 20** caracteres (letras, números, espacios, _ o -)."
    await get_or_create_user(user_id, username)
    if await clan_of(user_id):
        return False, "Ya perteneces a un clan. Sal primero con `/clan salir`."
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT 1 FROM clans WHERE name = ? COLLATE NOCASE", (name,)) as cur:
            if await cur.fetchone():
                await db.rollback()
                return False, "Ya existe un clan con ese nombre."
        cur = await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?",
            (CLAN_CREATE_COST, user_id, CLAN_CREATE_COST),
        )
        if cur.rowcount == 0:
            await db.rollback()
            return False, f"Crear un clan cuesta **{CLAN_CREATE_COST:,}** 🪙 y no te alcanza."
        now = datetime.utcnow().isoformat()
        cur = await db.execute(
            "INSERT INTO clans (name, owner_id, bank, open, created_at) VALUES (?, ?, 0, 1, ?)", (name, user_id, now)
        )
        await db.execute("INSERT INTO clan_members (user_id, clan_id, joined_at) VALUES (?, ?, ?)",
                         (user_id, cur.lastrowid, now))
        await db.commit()
    await feature_hook(user_id, "clan_joined")
    return True, f"🛡️ ¡Clan **{name}** creado! Invita gente con `/clan invitar` o déjalo abierto para que usen `/clan unirse`."


async def clan_join(user_id: str, username: str, name: str) -> tuple[bool, str]:
    await get_or_create_user(user_id, username)
    if await clan_of(user_id):
        return False, "Ya perteneces a un clan. Sal primero con `/clan salir`."
    clan = await clan_by_name(name)
    if not clan:
        return False, "No encontré ese clan."
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT COUNT(*) FROM clan_members WHERE clan_id=?", (clan["id"],)) as cur:
            count = (await cur.fetchone())[0]
        if count >= CLAN_MAX_MEMBERS:
            await db.rollback()
            return False, f"Ese clan está lleno ({CLAN_MAX_MEMBERS}/{CLAN_MAX_MEMBERS})."
        async with db.execute("SELECT 1 FROM clan_invites WHERE clan_id=? AND user_id=?", (clan["id"], user_id)) as cur:
            invited = await cur.fetchone() is not None
        if not clan["open"] and not invited:
            await db.rollback()
            return False, "Ese clan es **cerrado**: necesitas una invitación del líder."
        await db.execute("INSERT INTO clan_members (user_id, clan_id, joined_at) VALUES (?, ?, ?)",
                         (user_id, clan["id"], datetime.utcnow().isoformat()))
        await db.execute("DELETE FROM clan_invites WHERE user_id=?", (user_id,))
        await db.commit()
    await feature_hook(user_id, "clan_joined")
    return True, f"✅ Te uniste al clan **{clan['name']}**."


async def clan_leave(user_id: str) -> tuple[bool, str]:
    clan = await clan_of(user_id)
    if not clan:
        return False, "No perteneces a ningún clan."
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        await db.execute("DELETE FROM clan_members WHERE user_id=?", (user_id,))
        async with db.execute(
            "SELECT user_id FROM clan_members WHERE clan_id=? ORDER BY joined_at, user_id", (clan["id"],)
        ) as cur:
            remaining = [r[0] for r in await cur.fetchall()]
        if not remaining:
            # ultimo en salir: el clan se disuelve y el banco es suyo
            await db.execute("UPDATE users SET balance = MIN(balance + ?, ?) WHERE user_id=?",
                             (clan["bank"], MAX_BALANCE, user_id))
            await db.execute("DELETE FROM clans WHERE id=?", (clan["id"],))
            await db.execute("DELETE FROM clan_invites WHERE clan_id=?", (clan["id"],))
            await db.execute("DELETE FROM clan_missions WHERE clan_id=?", (clan["id"],))
            msg = f"Saliste y el clan **{clan['name']}** se disolvió. Recibiste **{clan['bank']:,}** 🪙 del banco."
        else:
            if clan["owner_id"] == user_id:
                await db.execute("UPDATE clans SET owner_id=? WHERE id=?", (remaining[0], clan["id"]))
                msg = f"Saliste de **{clan['name']}**. El liderazgo pasó a <@{remaining[0]}>."
            else:
                msg = f"Saliste del clan **{clan['name']}**."
        await db.commit()
    return True, msg


async def clan_deposit(user_id: str, amount_text: str) -> tuple[bool, str]:
    clan = await clan_of(user_id)
    if not clan:
        return False, "No perteneces a ningún clan."
    balance = await get_balance(user_id)
    amount = parse_amount_or_all(amount_text, balance)
    if amount is None or amount <= 0:
        return False, "Escribe una cantidad válida (`all`, `5m`, `500k`...)."
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (amount, user_id, amount)
        )
        if cur.rowcount == 0:
            await db.rollback()
            return False, f"No tienes **{amount:,}** 🪙 en la cartera."
        await db.execute("UPDATE clans SET bank = MIN(bank + ?, ?) WHERE id=?", (amount, MAX_BALANCE, clan["id"]))
        async with db.execute("SELECT bank FROM clans WHERE id=?", (clan["id"],)) as cur:
            bank = (await cur.fetchone())[0]
        await db.commit()
    return True, f"💰 Depositaste **{amount:,}** 🪙 en el banco de **{clan['name']}**. Banco: **{bank:,}** 🪙."


async def clan_withdraw(user_id: str, amount_text: str, target_id: str | None = None) -> tuple[bool, str]:
    clan = await clan_of(user_id)
    if not clan:
        return False, "No perteneces a ningún clan."
    if clan["owner_id"] != user_id:
        return False, "Solo el líder puede sacar monedas del banco del clan."
    amount = parse_amount_or_all(amount_text, clan["bank"])
    if amount is None or amount <= 0:
        return False, "Escribe una cantidad válida (`all`, `5m`, `500k`...)."
    target_id = target_id or user_id
    if target_id not in await clan_member_ids(clan["id"]):
        return False, "Solo puedes enviar monedas a miembros del clan."
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute("UPDATE clans SET bank = bank - ? WHERE id=? AND bank >= ?", (amount, clan["id"], amount))
        if cur.rowcount == 0:
            await db.rollback()
            return False, f"El banco del clan solo tiene **{clan['bank']:,}** 🪙."
        await db.execute("UPDATE users SET balance = MIN(balance + ?, ?) WHERE user_id=?",
                         (amount, MAX_BALANCE, target_id))
        await db.commit()
    return True, f"🏦 Sacaste **{amount:,}** 🪙 del banco de **{clan['name']}** y se las diste a <@{target_id}>."


async def clan_invite(owner_id: str, target_id: str) -> tuple[bool, str]:
    clan = await clan_of(owner_id)
    if not clan or clan["owner_id"] != owner_id:
        return False, "Solo el líder de un clan puede invitar."
    if await clan_of(target_id):
        return False, "Esa persona ya está en un clan."
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO clan_invites (clan_id, user_id) VALUES (?, ?)", (clan["id"], target_id))
        await db.commit()
    return True, f"📨 Invitaste a <@{target_id}> a **{clan['name']}**. Que use `/clan unirse {clan['name']}`."


async def clan_kick(owner_id: str, target_id: str) -> tuple[bool, str]:
    clan = await clan_of(owner_id)
    if not clan or clan["owner_id"] != owner_id:
        return False, "Solo el líder puede expulsar miembros."
    if target_id == owner_id:
        return False, "No puedes expulsarte a ti mismo; usa `/clan salir`."
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM clan_members WHERE user_id=? AND clan_id=?", (target_id, clan["id"]))
        await db.commit()
    if cur.rowcount == 0:
        return False, "Esa persona no está en tu clan."
    return True, f"👢 <@{target_id}> fue expulsado de **{clan['name']}**."


async def clan_set_open(owner_id: str, is_open: bool) -> tuple[bool, str]:
    clan = await clan_of(owner_id)
    if not clan or clan["owner_id"] != owner_id:
        return False, "Solo el líder puede cambiar el acceso."
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE clans SET open=? WHERE id=?", (1 if is_open else 0, clan["id"]))
        await db.commit()
    return True, "🔓 El clan ahora es **abierto**." if is_open else "🔒 El clan ahora es **cerrado** (solo con invitación)."


async def clan_disband(owner_id: str) -> tuple[bool, str]:
    clan = await clan_of(owner_id)
    if not clan or clan["owner_id"] != owner_id:
        return False, "Solo el líder puede disolver el clan."
    members = await clan_member_ids(clan["id"])
    share, extra = divmod(clan["bank"], len(members))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        for uid in members:
            await db.execute("UPDATE users SET balance = MIN(balance + ?, ?) WHERE user_id=?",
                             (share + (extra if uid == owner_id else 0), MAX_BALANCE, uid))
        await db.execute("DELETE FROM clan_members WHERE clan_id=?", (clan["id"],))
        await db.execute("DELETE FROM clan_invites WHERE clan_id=?", (clan["id"],))
        await db.execute("DELETE FROM clan_missions WHERE clan_id=?", (clan["id"],))
        await db.execute("DELETE FROM clans WHERE id=?", (clan["id"],))
        await db.commit()
    return True, f"💥 El clan **{clan['name']}** fue disuelto. El banco (**{clan['bank']:,}** 🪙) se repartió entre {len(members)} miembro(s)."


async def build_clan_info_embed(clan: dict) -> discord.Embed:
    members = await clan_member_ids(clan["id"])
    async with aiosqlite.connect(DB_PATH) as db:
        placeholders = ",".join("?" for _ in members)
        async with db.execute(
            f"SELECT user_id, username FROM users WHERE user_id IN ({placeholders})", members
        ) as cur:
            names = dict(await cur.fetchall())
    lines = [f"{'👑' if uid == clan['owner_id'] else '•'} **{names.get(uid, uid)}**" for uid in members]
    embed = discord.Embed(title=f"🛡️ Clan {clan['name']}", color=0x3498DB)
    embed.add_field(name="🏦 Banco", value=f"**{clan['bank']:,}** 🪙", inline=True)
    embed.add_field(name="👥 Miembros", value=f"{len(members)}/{CLAN_MAX_MEMBERS}", inline=True)
    embed.add_field(name="🚪 Acceso", value="Abierto" if clan["open"] else "Cerrado", inline=True)
    embed.add_field(name="Integrantes", value="\n".join(lines)[:1024], inline=False)
    return embed


async def build_clan_missions_embed(clan: dict) -> discord.Embed:
    wk = week_key()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT mission_key, progress, done FROM clan_missions WHERE clan_id=? AND week_key=?", (clan["id"], wk)
        ) as cur:
            state = {r[0]: (r[1], r[2]) for r in await cur.fetchall()}
    embed = discord.Embed(title=f"📋 Misiones semanales — {clan['name']}", color=0x9B59B6)
    for mkey, mission in CLAN_MISSIONS.items():
        progress, done = state.get(mkey, (0, 0))
        status = "✅ **¡Completada!**" if done else f"`[{_bar(progress, mission['goal'])}]` {progress}/{mission['goal']}"
        embed.add_field(
            name=f"{mission['name']} — +{mission['reward']:,} 🪙",
            value=f"{mission['desc']}\n{status}",
            inline=False,
        )
    embed.set_footer(text="El premio va al banco del clan · se reinicia el lunes 00:00 UTC")
    return embed


async def clan_name_autocomplete(interaction: discord.Interaction, current: str):
    t = _plain(current)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT c.name, c.open, (SELECT COUNT(*) FROM clan_members m WHERE m.clan_id=c.id), "
            "(SELECT 1 FROM clan_invites i WHERE i.clan_id=c.id AND i.user_id=?) "
            "FROM clans c ORDER BY c.bank DESC LIMIT 50",
            (str(interaction.user.id),),
        ) as cur:
            rows = await cur.fetchall()
    choices = []
    for name, is_open, count, invited in rows:
        if t and t not in _plain(name):
            continue
        tag = "📨 invitación" if invited else ("abierto" if is_open else "cerrado")
        choices.append(app_commands.Choice(name=f"{name} ({count}/{CLAN_MAX_MEMBERS} · {tag})"[:100], value=name))
    return choices[:25]


clan_group = app_commands.Group(name="clan", description="Clanes: banco compartido y misiones en grupo", guild_only=True)
tree.add_command(clan_group)


async def _clan_reply(interaction: discord.Interaction, result: tuple[bool, str]):
    ok, text = result
    await interaction.response.send_message(text if ok else f"❌ {text}", ephemeral=not ok)


@clan_group.command(name="crear", description=f"Crea un clan (cuesta {CLAN_CREATE_COST:,} monedas)")
@app_commands.describe(nombre="Nombre del clan (3-20 caracteres)")
async def clan_crear(interaction: discord.Interaction, nombre: str):
    await _clan_reply(interaction, await clan_create(str(interaction.user.id), interaction.user.name, nombre))


@clan_group.command(name="unirse", description="Únete a un clan abierto o al que te invitó")
@app_commands.describe(nombre="Clan al que quieres unirte")
async def clan_unirse(interaction: discord.Interaction, nombre: str):
    await _clan_reply(interaction, await clan_join(str(interaction.user.id), interaction.user.name, nombre))


clan_unirse.autocomplete("nombre")(clan_name_autocomplete)


@clan_group.command(name="salir", description="Sal de tu clan")
async def clan_salir(interaction: discord.Interaction):
    await _clan_reply(interaction, await clan_leave(str(interaction.user.id)))


@clan_group.command(name="info", description="Mira un clan (por defecto, el tuyo)")
@app_commands.describe(nombre="Nombre del clan (opcional)")
async def clan_info(interaction: discord.Interaction, nombre: _LoanOptional[str] = None):
    clan = await clan_by_name(nombre) if nombre else await clan_of(str(interaction.user.id))
    if not clan:
        await interaction.response.send_message("❌ No encontré ese clan (o no estás en ninguno).", ephemeral=True)
        return
    await interaction.response.send_message(embed=await build_clan_info_embed(clan))


clan_info.autocomplete("nombre")(clan_name_autocomplete)


@clan_group.command(name="depositar", description="Deposita monedas en el banco compartido del clan")
@app_commands.describe(cantidad="Cantidad (acepta all, 5m, 500k)")
async def clan_depositar(interaction: discord.Interaction, cantidad: str):
    await _clan_reply(interaction, await clan_deposit(str(interaction.user.id), cantidad))


@clan_group.command(name="retirar", description="[Líder] Saca monedas del banco del clan para ti o un miembro")
@app_commands.describe(cantidad="Cantidad (acepta all, 5m, 500k)", usuario="Miembro que las recibe (por defecto, tú)")
async def clan_retirar(interaction: discord.Interaction, cantidad: str, usuario: _LoanOptional[discord.Member] = None):
    await _clan_reply(interaction, await clan_withdraw(
        str(interaction.user.id), cantidad, str(usuario.id) if usuario else None))


@clan_group.command(name="invitar", description="[Líder] Invita a un jugador a tu clan")
@app_commands.describe(usuario="Jugador a invitar")
async def clan_invitar(interaction: discord.Interaction, usuario: discord.Member):
    if usuario.bot:
        await interaction.response.send_message("❌ No puedes invitar a un bot.", ephemeral=True)
        return
    await _clan_reply(interaction, await clan_invite(str(interaction.user.id), str(usuario.id)))


@clan_group.command(name="expulsar", description="[Líder] Expulsa a un miembro del clan")
@app_commands.describe(usuario="Miembro a expulsar")
async def clan_expulsar(interaction: discord.Interaction, usuario: discord.Member):
    await _clan_reply(interaction, await clan_kick(str(interaction.user.id), str(usuario.id)))


@clan_group.command(name="acceso", description="[Líder] Haz el clan abierto (cualquiera entra) o cerrado (solo invitados)")
@app_commands.describe(modo="Abierto o cerrado")
@app_commands.choices(modo=[
    app_commands.Choice(name="Abierto", value="abierto"),
    app_commands.Choice(name="Cerrado (solo invitación)", value="cerrado"),
])
async def clan_acceso(interaction: discord.Interaction, modo: str):
    await _clan_reply(interaction, await clan_set_open(str(interaction.user.id), modo == "abierto"))


@clan_group.command(name="misiones", description="Mira las misiones semanales de tu clan")
async def clan_misiones(interaction: discord.Interaction):
    clan = await clan_of(str(interaction.user.id))
    if not clan:
        await interaction.response.send_message("❌ No perteneces a ningún clan.", ephemeral=True)
        return
    await interaction.response.send_message(embed=await build_clan_missions_embed(clan))


@clan_group.command(name="top", description="Ranking de clanes por banco")
async def clan_top(interaction: discord.Interaction):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT c.name, c.bank, (SELECT COUNT(*) FROM clan_members m WHERE m.clan_id=c.id) "
            "FROM clans c ORDER BY c.bank DESC LIMIT 10"
        ) as cur:
            rows = await cur.fetchall()
    if not rows:
        await interaction.response.send_message("❌ Todavía no hay clanes. Crea el primero con `/clan crear`.", ephemeral=True)
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"{medals[i] if i < 3 else f'**#{i + 1}**'} **{name}** — {bank:,} 🪙 · {count} miembro(s)"
             for i, (name, bank, count) in enumerate(rows)]
    await interaction.response.send_message(embed=discord.Embed(
        title="🏆 Top de clanes", description="\n".join(lines), color=0xFFD700))


@clan_group.command(name="disolver", description="[Líder] Disuelve el clan y reparte el banco entre los miembros")
@app_commands.describe(confirmar="Pon True para confirmar")
async def clan_disolver(interaction: discord.Interaction, confirmar: bool):
    if not confirmar:
        await interaction.response.send_message("❌ Marca `confirmar: True` si de verdad quieres disolver el clan.", ephemeral=True)
        return
    await _clan_reply(interaction, await clan_disband(str(interaction.user.id)))


async def clan_handle_prefix(message: discord.Message, args: list[str]):
    """Permite usar todos los subcomandos de /clan con el prefijo de texto ','."""
    if message.guild is None:
        await message.channel.send("❌ Los comandos del clan solo se pueden usar dentro de un servidor.")
        return

    if not args or args[0].lower() in {"ayuda", "help"}:
        embed = discord.Embed(
            title="🛡️ Comandos del clan",
            description=(
                "También puedes usar los comandos slash con `/clan`.\n"
                "Los nombres con espacios se escriben completos; para usuarios, menciona a la persona."
            ),
            color=0x3498DB,
        )
        embed.add_field(
            name="Miembros",
            value=(
                "`,clan crear <nombre>`\n"
                "`,clan unirse <nombre>`\n"
                "`,clan salir`\n"
                "`,clan info [nombre]`\n"
                "`,clan misiones` · `,clan top`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Banco y liderazgo",
            value=(
                "`,clan depositar <cantidad>`\n"
                "`,clan retirar <cantidad> [@miembro]`\n"
                "`,clan invitar @usuario` · `,clan expulsar @usuario`\n"
                "`,clan acceso abierto|cerrado`\n"
                "`,clan disolver confirmar`"
            ),
            inline=False,
        )
        await message.channel.send(embed=embed)
        return

    subcommand = args[0].lower()
    params = args[1:]
    user_id = str(message.author.id)

    async def send_result(result: tuple[bool, str]):
        ok, text = result
        await message.channel.send(text if ok else f"❌ {text}")

    async def resolve_member(token: str) -> discord.Member | None:
        match = re.fullmatch(r"(?:<@!?(\d+)>|(\d+))", token)
        if not match:
            return None
        target_id = int(match.group(1) or match.group(2))
        member = message.guild.get_member(target_id)
        if member:
            return member
        try:
            return await message.guild.fetch_member(target_id)
        except (discord.NotFound, discord.HTTPException):
            return None

    if subcommand == "crear":
        if not params:
            await message.channel.send("Uso: `,clan crear <nombre>`.")
            return
        await send_result(await clan_create(user_id, message.author.name, " ".join(params)))
    elif subcommand == "unirse":
        if not params:
            await message.channel.send("Uso: `,clan unirse <nombre>`.")
            return
        await send_result(await clan_join(user_id, message.author.name, " ".join(params)))
    elif subcommand == "salir":
        await send_result(await clan_leave(user_id))
    elif subcommand == "info":
        clan = await clan_by_name(" ".join(params)) if params else await clan_of(user_id)
        if not clan:
            await message.channel.send("❌ No encontré ese clan (o no estás en ninguno).")
            return
        await message.channel.send(embed=await build_clan_info_embed(clan))
    elif subcommand == "depositar":
        if len(params) != 1:
            await message.channel.send("Uso: `,clan depositar <cantidad>`.")
            return
        await send_result(await clan_deposit(user_id, params[0]))
    elif subcommand == "retirar":
        if not 1 <= len(params) <= 2:
            await message.channel.send("Uso: `,clan retirar <cantidad> [@miembro]`.")
            return
        target_id = None
        if len(params) == 2:
            member = await resolve_member(params[1])
            if member is None:
                await message.channel.send("❌ Menciona a un miembro del servidor para recibir las monedas.")
                return
            target_id = str(member.id)
        await send_result(await clan_withdraw(user_id, params[0], target_id))
    elif subcommand in {"invitar", "expulsar"}:
        if len(params) != 1:
            await message.channel.send(f"Uso: `,clan {subcommand} @usuario`.")
            return
        member = await resolve_member(params[0])
        if member is None:
            await message.channel.send("❌ Menciona a un miembro de este servidor.")
            return
        if subcommand == "invitar":
            if member.bot:
                await message.channel.send("❌ No puedes invitar a un bot.")
                return
            await send_result(await clan_invite(user_id, str(member.id)))
        else:
            await send_result(await clan_kick(user_id, str(member.id)))
    elif subcommand == "acceso":
        if len(params) != 1 or params[0].lower() not in {"abierto", "cerrado"}:
            await message.channel.send("Uso: `,clan acceso abierto` o `,clan acceso cerrado`.")
            return
        await send_result(await clan_set_open(user_id, params[0].lower() == "abierto"))
    elif subcommand == "misiones":
        clan = await clan_of(user_id)
        if not clan:
            await message.channel.send("❌ No perteneces a ningún clan.")
            return
        await message.channel.send(embed=await build_clan_missions_embed(clan))
    elif subcommand == "top":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT c.name, c.bank, (SELECT COUNT(*) FROM clan_members m WHERE m.clan_id=c.id) "
                "FROM clans c ORDER BY c.bank DESC LIMIT 10"
            ) as cur:
                rows = await cur.fetchall()
        if not rows:
            await message.channel.send("❌ Todavía no hay clanes. Crea el primero con `,clan crear <nombre>`.")
            return
        medals = ["🥇", "🥈", "🥉"]
        lines = [
            f"{medals[i] if i < 3 else f'**#{i + 1}**'} **{name}** — {bank:,} 🪙 · {count} miembro(s)"
            for i, (name, bank, count) in enumerate(rows)
        ]
        await message.channel.send(
            embed=discord.Embed(title="🏆 Top de clanes", description="\n".join(lines), color=0xFFD700)
        )
    elif subcommand == "disolver":
        if len(params) != 1 or params[0].lower() != "confirmar":
            await message.channel.send("Para confirmar, escribe `,clan disolver confirmar`.")
            return
        await send_result(await clan_disband(user_id))
    else:
        await message.channel.send(
            f"❌ No reconozco el subcomando `{subcommand}`. Escribe `,clan ayuda` para ver los comandos."
        )


# =====================================================================
#  MINES  ·  revela diamantes, evita las minas y retirate a tiempo
# =====================================================================
def mines_multiplier(mines: int, revealed: int) -> float:
    if revealed <= 0:
        return 1.0
    mult = 1.0
    for i in range(revealed):
        mult *= (MINES_TILES - i) / (MINES_TILES - mines - i)
    return mult * MINES_PAYOUT_FACTOR


class MinesButton(discord.ui.Button):
    def __init__(self, idx: int):
        super().__init__(emoji="❔", style=discord.ButtonStyle.secondary, row=idx // 5)
        self.idx = idx

    async def callback(self, interaction: discord.Interaction):
        await self.view.reveal(interaction, self)


class MinesView(GuildView):
    def __init__(self, user_id: str, bet: int, mines: int):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.bet = bet
        self.mines = mines
        self.mine_set = set(random.sample(range(MINES_TILES), mines))
        self.revealed: set[int] = set()
        self.finished = False
        self.message: discord.Message | None = None
        self.tile_buttons = [MinesButton(i) for i in range(MINES_TILES)]
        for button in self.tile_buttons:
            self.add_item(button)
        self.cash_button = discord.ui.Button(label="💰 Retirar", style=discord.ButtonStyle.success, row=4, disabled=True)
        self.cash_button.callback = self.cashout_callback
        self.add_item(self.cash_button)

    def current_payout(self) -> int:
        return int(self.bet * mines_multiplier(self.mines, len(self.revealed)))

    def make_embed(self, title: str = "💎 Mines", color: int = 0x9B59B6, footer: str | None = None) -> discord.Embed:
        k = len(self.revealed)
        embed = discord.Embed(title=title, color=color)
        lines = [
            f"💵 Apuesta: **{self.bet:,}** 🪙 · 💣 Minas: **{self.mines}**",
            f"💎 Diamantes revelados: **{k}/{MINES_TILES - self.mines}**",
            f"📈 Multiplicador: **x{mines_multiplier(self.mines, k):.2f}** → **{self.current_payout():,}** 🪙",
        ]
        if not self.finished and k < MINES_TILES - self.mines:
            nxt = int(self.bet * mines_multiplier(self.mines, k + 1))
            lines.append(f"➡️ Siguiente diamante: **x{mines_multiplier(self.mines, k + 1):.2f}** ({nxt:,} 🪙)")
        embed.description = "\n".join(lines)
        if footer:
            embed.set_footer(text=footer)
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta partida no es tuya.", ephemeral=True)
            return False
        return True

    def _reveal_board(self, hit: int | None = None):
        for button in self.tile_buttons:
            button.disabled = True
            if button.idx in self.mine_set:
                button.emoji = "💣"
                button.style = discord.ButtonStyle.danger if button.idx == hit else discord.ButtonStyle.secondary
            elif button.idx in self.revealed:
                button.emoji = "💎"
                button.style = discord.ButtonStyle.success
            else:
                button.emoji = "💎"
                button.style = discord.ButtonStyle.secondary
        self.cash_button.disabled = True

    async def reveal(self, interaction: discord.Interaction, button: MinesButton):
        if self.finished:
            await interaction.response.defer()
            return
        if button.idx in self.mine_set:
            self.finished = True
            self._reveal_board(hit=button.idx)
            self.stop()
            await log_bet(self.user_id, "💎 Mines", self.bet, -self.bet)
            embed = self.make_embed("💥 ¡Boom! Pisaste una mina", 0xFF4444, f"Perdiste {self.bet:,} 🪙")
            await interaction.response.edit_message(embed=embed, view=self)
            return
        self.revealed.add(button.idx)
        button.emoji = "💎"
        button.style = discord.ButtonStyle.success
        button.disabled = True
        self.cash_button.disabled = False
        if len(self.revealed) >= MINES_TILES - self.mines:
            await self._cashout(interaction, perfect=True)
            return
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    async def cashout_callback(self, interaction: discord.Interaction):
        if self.finished or not self.revealed:
            await interaction.response.defer()
            return
        await self._cashout(interaction)

    async def _cashout(self, interaction: discord.Interaction | None, perfect: bool = False):
        self.finished = True
        payout = self.current_payout()
        await update_balance(self.user_id, payout)
        await log_bet(self.user_id, "💎 Mines", self.bet, payout - self.bet)
        if payout > self.bet:
            await feature_hook(self.user_id, "mines_cashout")
        self._reveal_board()
        self.stop()
        profit = payout - self.bet
        title = "🏆 ¡Tablero limpio!" if perfect else "💰 Te retiraste a tiempo"
        embed = self.make_embed(title, 0x00FF88, f"Ganaste {profit:+,} 🪙")
        if interaction is not None:
            await interaction.response.edit_message(embed=embed, view=self)
        elif self.message is not None:
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass

    async def on_timeout(self):
        if self.finished:
            return
        if self.revealed:
            await self._cashout(None)  # tiempo agotado: se retira solo
            return
        self.finished = True
        await update_balance(self.user_id, self.bet)  # no reveló nada: se devuelve la apuesta
        self._reveal_board()
        if self.message is not None:
            try:
                await self.message.edit(embed=self.make_embed("⏰ Tiempo agotado", 0x95A5A6, "Apuesta devuelta"), view=self)
            except discord.HTTPException:
                pass


async def mines_create(user_id: str, username: str, bet_text: str, mines: int) -> tuple[str | None, MinesView | None]:
    if not 1 <= mines <= MINES_MAX:
        return f"Las minas deben ser entre **1** y **{MINES_MAX}**.", None
    await get_or_create_user(user_id, username)
    balance = await get_balance(user_id)
    bet = parse_amount_or_all(bet_text, balance)
    if bet is None or bet <= 0:
        return "Escribe una apuesta válida (`all`, `5m`, `500k`...).", None
    if bet > balance:
        return f"Tienes **{balance:,}** 🪙 y quieres apostar **{bet:,}** 🪙.", None
    await update_balance(user_id, -bet)
    await track_mission(user_id, "mines_played")
    return None, MinesView(user_id, bet, mines)


@tree.command(name="mines", description="Buscaminas: revela diamantes, evita las minas y retírate a tiempo")
@app_commands.describe(cantidad="Apuesta (acepta all, 5m, 500k)", minas=f"Cantidad de minas (1-{MINES_MAX}, más minas = más premio)")
async def mines_command(interaction: discord.Interaction, cantidad: str, minas: app_commands.Range[int, 1, MINES_MAX] = 3):
    error, view = await mines_create(str(interaction.user.id), interaction.user.name, cantidad, minas)
    if error:
        await interaction.response.send_message(embed=_err_embed("No se pudo empezar", error), ephemeral=True)
        return
    await interaction.response.send_message(embed=view.make_embed(), view=view)
    view.message = await interaction.original_response()


# =====================================================================
#  PREFIJO para los comandos nuevos (,top ,logros ,carcel ,fianza ...)
# =====================================================================
async def features_handle_prefix(message: discord.Message, cmd: str, args: list) -> bool:
    uid = str(message.author.id)
    _last_channel[uid] = message.channel
    if await jail_block_prefix(message, cmd):
        return True
    if await shop_handle_prefix(message, cmd, args):
        return True

    if cmd == "top":
        await message.channel.send(embed=await build_top_embed(uid))
        return True
    if cmd in ("logros", "achievements"):
        target = message.mentions[0] if message.mentions else message.author
        await message.channel.send(embed=await logros_embed_for(str(target.id), target.display_name))
        return True
    if cmd in ("carcel", "cárcel", "jail"):
        target = message.mentions[0] if message.mentions else message.author
        remaining = await jail_remaining(str(target.id))
        if remaining is None:
            await message.channel.send(f"✅ **{target.display_name}** no está en la cárcel.")
        else:
            await message.channel.send(embed=jail_embed(remaining))
        return True
    if cmd in ("fianza", "bail"):
        await message.channel.send(embed=await jail_pay_bail(uid, message.author.name))
        return True
    if cmd in ("misprestamos", "misprestamosroles"):
        await message.channel.send(embed=await build_misprestamos_embed(uid))
        return True
    if cmd == "evento":
        mult, text = await collect_event_info()
        await message.channel.send(embed=discord.Embed(
            title="🎉 Eventos del casino", description=text, color=0x00FF88 if mult > 1 else 0x95A5A6))
        return True
    if cmd == "mines":
        if not args:
            await message.channel.send("❌ Uso: `,mines <cantidad|all> [minas 1-10]` — ej: `,mines 1m 3`")
            return True
        mines = 3
        if len(args) > 1:
            if not args[1].isdigit():
                await message.channel.send("❌ Las minas deben ser un número del 1 al 10.")
                return True
            mines = int(args[1])
        error, view = await mines_create(uid, message.author.name, args[0], mines)
        if error:
            await message.channel.send(embed=_err_embed("No se pudo empezar", error))
            return True
        view.message = await message.channel.send(embed=view.make_embed(), view=view)
        return True
    if cmd == "hilo":
        if not args:
            await message.channel.send("❌ Uso: `,hilo <cantidad|all>` — ej: `,hilo 1m`")
            return True
        error, view = await hilo_create(uid, message.author.name, args[0], message.author.display_name,
                                        message.author.display_avatar.url)
        if error:
            await message.channel.send(embed=_err_embed("No se pudo empezar", error))
            return True
        view.message = await message.channel.send(embed=view.make_embed(), view=view)
        return True
    return False


# =====================================================================
#  /removemoney con "all"
# =====================================================================
async def perform_removemoney(target: discord.Member, amount_text: str, include_bank: bool = False):
    """Quita dinero a un usuario. Devuelve un Embed, o un str con el error."""
    target_id = str(target.id)
    await get_or_create_user(target_id, target.name)
    current = await get_balance(target_id)
    text = str(amount_text).strip().lower()
    if text in ALL_WORDS:
        deduct = current
    else:
        amount = loan_parse_amount(text)
        if amount is None or amount <= 0:
            return "❌ La cantidad debe ser un número mayor a 0, o `all` para quitar todo."
        deduct = min(amount, current)
    await update_balance(target_id, -deduct)
    bank_removed = 0
    if include_bank:
        bank_removed = await get_bank(target_id)
        if bank_removed:
            await update_bank(target_id, -bank_removed)
    new_balance = await get_balance(target_id)
    description = f"Se quitaron **{deduct:,}** 🪙 de la cartera de {target.mention}."
    if include_bank:
        description += f"\n🏦 También se vació el banco: **{bank_removed:,}** 🪙."
    description += f"\nNuevo saldo: **{new_balance:,}** 🪙"
    return discord.Embed(title="✅ Dinero Eliminado", description=description, color=0xFFAA00)


async def ftorneo_charge_host(user_id: str, entry_fee: int) -> str | None:
    """Cobra la apuesta de entrada al organizador. Devuelve un error o None."""
    if entry_fee <= 0:
        return None
    balance = await get_balance(user_id)
    if balance < entry_fee:
        return f"❌ La apuesta de entrada es **{entry_fee:,}** 🪙 y tienes **{balance:,}** 🪙."
    await update_balance(user_id, -entry_fee)
    return None


# =====================================================================
#  ECONOMÍA POR SERVIDOR · BLACKLIST · HI-LO
# =====================================================================
async def init_global_db():
    os.makedirs(os.path.dirname(GLOBAL_DB_PATH) or ".", exist_ok=True)
    async with aiosqlite.connect(GLOBAL_DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, value TEXT)")
        await db.execute(
            """CREATE TABLE IF NOT EXISTS blacklist (
                user_id TEXT PRIMARY KEY, username TEXT, reason TEXT, added_by TEXT, added_at TEXT)"""
        )
        await db.execute("CREATE TABLE IF NOT EXISTS guild_dbs (guild_id TEXT PRIMARY KEY, path TEXT NOT NULL)")
        await db.execute(
            """CREATE TABLE IF NOT EXISTS config_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, user_id TEXT NOT NULL,
                user_name TEXT NOT NULL, key TEXT NOT NULL, old TEXT, new TEXT)"""
        )
        await db.commit()


def _backup_sqlite(src: str, dst: str):
    """Copia una base SQLite de forma consistente (incluye lo que esté en el WAL)."""
    source = _sqlite3.connect(src)
    try:
        target = _sqlite3.connect(dst)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()


def _read_legacy_panel_settings() -> list:
    try:
        conn = _sqlite3.connect(LEGACY_DB_PATH)
        try:
            return conn.execute("SELECT key, value FROM bot_settings WHERE key LIKE 'cfg:%'").fetchall()
        finally:
            conn.close()
    except _sqlite3.Error:
        return []


async def _map_guild(guild_id: str, path: str):
    _guild_paths[guild_id] = path
    async with aiosqlite.connect(GLOBAL_DB_PATH) as db:
        await db.execute(
            "INSERT INTO guild_dbs (guild_id, path) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET path=excluded.path",
            (guild_id, path),
        )
        await db.commit()


async def load_guild_map():
    async with aiosqlite.connect(GLOBAL_DB_PATH) as db:
        async with db.execute("SELECT guild_id, path FROM guild_dbs") as cur:
            for guild_id, path in await cur.fetchall():
                _guild_paths[guild_id] = path


async def run_economy_migration():
    """Una sola vez: cada servidor actual recibe una copia de la economía vieja (compartida).

    Desde ese momento cada servidor evoluciona por separado. Los servidores que se agreguen
    después empiezan de cero. Con LEGACY_GUILD_ID solo ese servidor recibe la economía vieja.
    """
    if await setting_get("economy_split_done", scope="global"):
        return
    if os.path.exists(LEGACY_DB_PATH):
        only = os.environ.get("LEGACY_GUILD_ID", "").strip()
        for guild in list(client.guilds):
            if only and str(guild.id) != only:
                continue
            dest = GUILD_DB_TEMPLATE.format(guild_id=guild.id)
            if not os.path.exists(dest):
                await asyncio.to_thread(_backup_sqlite, LEGACY_DB_PATH, dest)
            await _map_guild(str(guild.id), dest)
            print(f"Economía copiada al servidor {guild.name} ({guild.id}).")
        rows = await asyncio.to_thread(_read_legacy_panel_settings)
        if rows:
            async with aiosqlite.connect(GLOBAL_DB_PATH) as db:
                for key, value in rows:
                    await db.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)", (key, value))
                await db.commit()
    await setting_set("economy_split_done", "1", scope="global")


async def _init_guild_tables():
    await init_db()
    await init_shield_table()
    await loan_init_table()
    await init_role_loans_table()
    await init_extras_tables()
    await load_custom_items()


async def enter_guild(guild_id) -> None:
    """Fija el servidor actual (para esta tarea) y prepara su base de datos si hace falta."""
    global _guild_init_lock
    gid = str(guild_id)
    _current_guild.set(gid)
    if gid in _guild_ready:
        return
    if _guild_init_lock is None:
        _guild_init_lock = asyncio.Lock()
    async with _guild_init_lock:
        if gid in _guild_ready:
            return
        if gid not in _guild_paths:
            os.makedirs(os.path.dirname(GUILD_DB_TEMPLATE) or ".", exist_ok=True)
            await _map_guild(gid, GUILD_DB_TEMPLATE.format(guild_id=gid))
        await _init_guild_tables()
        _guild_ready.add(gid)


async def for_each_guild(fn):
    """Ejecuta una tarea una vez por servidor, cada una con su propia economía."""
    for guild in list(client.guilds):
        try:
            await enter_guild(guild.id)
            await fn()
        except Exception as exc:
            print(f"Error en {getattr(fn, '__name__', 'tarea')} (servidor {guild.id}): {exc}")


# ---------------------------------------------------------------- blacklist
BLACKLIST_OWNER_USERNAME = "jose_antonio972"
BLACKLIST_BLOCKED_TEXT = "🚫 Estás en la **blacklist**: ya no puedes usar la economía del bot."
_blacklist_ids: set = set()
BLACKLIST_EXEMPT_COMMANDS = {   # no son economía: siguen funcionando para todos
    "help", "guía", "guia", "blacklist", "ban", "unban", "kick", "mute", "unmute",
    "clear", "lock", "unlock", "addrole", "removerole",
}
BLACKLIST_EXEMPT_PREFIX = BLACKLIST_EXEMPT_COMMANDS | {"ayuda"}


async def load_blacklist():
    async with aiosqlite.connect(GLOBAL_DB_PATH) as db:
        async with db.execute("SELECT user_id FROM blacklist") as cur:
            _blacklist_ids.clear()
            _blacklist_ids.update(r[0] for r in await cur.fetchall())


async def blacklist_authorized(user) -> bool:
    """Solo jose_antonio972 (o los IDs de BLACKLIST_OWNER_IDS). La primera vez se fija su ID."""
    uid = str(user.id)
    env_ids = {x for x in re.split(r"[\s,;]+", os.environ.get("BLACKLIST_OWNER_IDS", "")) if x}
    if uid in env_ids:
        return True
    pinned = await setting_get("blacklist_owner_id", scope="global")
    if pinned:
        return uid == pinned
    if (getattr(user, "name", "") or "").lower() == BLACKLIST_OWNER_USERNAME:
        await setting_set("blacklist_owner_id", uid, scope="global")
        return True
    return False


async def blacklist_add(user_id: str, username: str, reason: str, added_by: str) -> bool:
    async with aiosqlite.connect(GLOBAL_DB_PATH) as db:
        cur = await db.execute(
            "INSERT OR IGNORE INTO blacklist (user_id, username, reason, added_by, added_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, reason, added_by, datetime.utcnow().isoformat()),
        )
        await db.commit()
        added = cur.rowcount == 1
    _blacklist_ids.add(user_id)
    return added


async def blacklist_remove(user_id: str) -> bool:
    async with aiosqlite.connect(GLOBAL_DB_PATH) as db:
        cur = await db.execute("DELETE FROM blacklist WHERE user_id=?", (user_id,))
        await db.commit()
        removed = cur.rowcount == 1
    _blacklist_ids.discard(user_id)
    return removed


async def blacklist_entries() -> list:
    async with aiosqlite.connect(GLOBAL_DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, username, reason, added_at FROM blacklist ORDER BY added_at DESC"
        ) as cur:
            return await cur.fetchall()


def build_blacklist_embed(rows: list) -> discord.Embed:
    embed = discord.Embed(title="🚫 Blacklist de economía", color=0xED4245)
    if not rows:
        embed.description = "La blacklist está vacía."
        return embed
    lines = []
    for uid, name, reason, _ts in rows[:40]:
        lines.append(f"<@{uid}> (`{name or uid}`)" + (f" — {reason}" if reason else ""))
    embed.description = "\n".join(lines)[:4000]
    embed.set_footer(text=f"{len(rows)} usuario(s) en la blacklist")
    return embed


def _blacklist_block_for(interaction: discord.Interaction) -> str | None:
    uid = str(interaction.user.id)
    if uid in _blacklist_ids:
        return BLACKLIST_BLOCKED_TEXT
    data = interaction.data or {}
    resolved = (data.get("resolved") or {}).get("users") or {}
    for target_id, info in resolved.items():
        if target_id != uid and target_id in _blacklist_ids:
            name = (info or {}).get("username", target_id)
            return f"🚫 **{name}** está en la blacklist: no puedes hacer acciones de economía con esa persona."
    return None


async def _enter_interaction(interaction: discord.Interaction) -> bool:
    """Para botones y formularios: fija el servidor y bloquea DMs y blacklist. False = ya se respondió."""
    try:
        if interaction.guild_id is None:
            message = "❌ La economía es por servidor: usa esto dentro de un servidor."
        else:
            await enter_guild(interaction.guild_id)
            message = BLACKLIST_BLOCKED_TEXT if str(interaction.user.id) in _blacklist_ids else None
    except Exception as exc:
        print(f"Error preparando el servidor: {exc}")
        message = "❌ No pude preparar la economía de este servidor. Inténtalo de nuevo."
    if message is None:
        return True
    try:
        await interaction.response.send_message(message, ephemeral=True)
    except Exception:
        pass
    return False


async def enter_message(message: discord.Message, cmd: str) -> bool:
    """Para comandos con prefijo: fija el servidor y bloquea DMs y blacklist."""
    _last_channel[str(message.author.id)] = message.channel
    if message.guild is None:
        if cmd in BLACKLIST_EXEMPT_PREFIX:
            return True   # ayuda y moderación no usan la economía
        await message.channel.send("❌ La economía es por servidor: usa los comandos dentro de un servidor.")
        return False
    try:
        await enter_guild(message.guild.id)
    except Exception as exc:
        print(f"Error preparando el servidor: {exc}")
        await message.channel.send("❌ No pude preparar la economía de este servidor. Inténtalo de nuevo.")
        return False
    if cmd in BLACKLIST_EXEMPT_PREFIX:
        return True
    author_id = str(message.author.id)
    if author_id in _blacklist_ids:
        await message.channel.send(BLACKLIST_BLOCKED_TEXT)
        return False
    for member in message.mentions:
        if str(member.id) != author_id and str(member.id) in _blacklist_ids:
            await message.channel.send(
                f"🚫 **{member.display_name}** está en la blacklist: no puedes hacer acciones de economía con esa persona.")
            return False
    return True


blacklist_group = app_commands.Group(
    name="blacklist", description="Gestiona la blacklist de la economía (solo el dueño del bot)"
)
tree.add_command(blacklist_group)


async def _blacklist_gate(interaction: discord.Interaction) -> bool:
    if await blacklist_authorized(interaction.user):
        return True
    await interaction.response.send_message(
        f"❌ Solo **{BLACKLIST_OWNER_USERNAME}** puede usar este comando.", ephemeral=True)
    return False


@blacklist_group.command(name="add", description="Mete a un usuario en la blacklist (no podrá usar la economía en ningún servidor)")
@app_commands.describe(usuario="Usuario a bloquear", razon="Motivo (opcional)")
async def blacklist_add_cmd(interaction: discord.Interaction, usuario: discord.User, razon: str = ""):
    if not await _blacklist_gate(interaction):
        return
    if usuario.bot or usuario.id == interaction.user.id:
        await interaction.response.send_message("❌ No puedes poner en la blacklist a un bot ni a ti mismo.", ephemeral=True)
        return
    added = await blacklist_add(str(usuario.id), usuario.name, razon.strip()[:200], str(interaction.user.id))
    await interaction.response.send_message(
        f"🚫 **{usuario.name}** {'fue añadido a' if added else 'ya estaba en'} la blacklist.", ephemeral=True)


@blacklist_group.command(name="remove", description="Saca a un usuario de la blacklist")
@app_commands.describe(usuario="Usuario a perdonar")
async def blacklist_remove_cmd(interaction: discord.Interaction, usuario: discord.User):
    if not await _blacklist_gate(interaction):
        return
    removed = await blacklist_remove(str(usuario.id))
    await interaction.response.send_message(
        f"✅ **{usuario.name}** salió de la blacklist." if removed else f"ℹ️ **{usuario.name}** no estaba en la blacklist.",
        ephemeral=True)


@blacklist_group.command(name="list", description="Muestra quién está en la blacklist")
async def blacklist_list_cmd(interaction: discord.Interaction):
    if not await _blacklist_gate(interaction):
        return
    await interaction.response.send_message(embed=build_blacklist_embed(await blacklist_entries()), ephemeral=True)


async def blacklist_handle_prefix(message: discord.Message, args: list):
    if not await blacklist_authorized(message.author):
        await message.channel.send(f"❌ Solo **{BLACKLIST_OWNER_USERNAME}** puede usar este comando.")
        return
    usage = "❌ Uso: `,blacklist add @usuario [razón]` · `,blacklist remove @usuario` · `,blacklist list`"
    sub = args[0].lower() if args else ""
    if sub in ("list", "lista"):
        await message.channel.send(embed=build_blacklist_embed(await blacklist_entries()))
        return
    if sub not in ("add", "agregar", "remove", "quitar"):
        await message.channel.send(usage)
        return
    target_id, rest = None, args[1:]
    if message.mentions:
        target_id = str(message.mentions[0].id)
        rest = [a for a in rest if not re.fullmatch(r"<@!?\d+>", a)]
    elif rest and rest[0].isdigit():
        target_id, rest = rest[0], rest[1:]
    if target_id is None:
        await message.channel.send(usage)
        return
    name = target_id
    try:
        user = client.get_user(int(target_id)) or await client.fetch_user(int(target_id))
        name = user.name
        if user.bot:
            await message.channel.send("❌ No puedes poner en la blacklist a un bot.")
            return
    except (discord.HTTPException, ValueError):
        pass
    if target_id == str(message.author.id):
        await message.channel.send("❌ No puedes ponerte a ti mismo en la blacklist.")
        return
    if sub in ("add", "agregar"):
        added = await blacklist_add(target_id, name, " ".join(rest)[:200], str(message.author.id))
        await message.channel.send(f"🚫 **{name}** {'fue añadido a' if added else 'ya estaba en'} la blacklist.")
    else:
        removed = await blacklist_remove(target_id)
        await message.channel.send(f"✅ **{name}** salió de la blacklist." if removed else f"ℹ️ **{name}** no estaba en la blacklist.")


# =====================================================================
#  HI-LO (mayor, menor o igual)  ·  ,hilo <cantidad>  y  /hilo
# =====================================================================
HILO_PAYOUT_FACTOR = 0.97          # 1.00 = pago justo; 0.97 = 3% de ventaja de la casa
HILO_DECKS = 3                     # barajas del mazo (156 cartas)
_HILO_RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
_HILO_SUITS = ["♠️", "♥️", "♦️", "♣️"]
_HILO_GUESS = {"higher": "mayor", "lower": "menor", "same": "igual"}


def hilo_new_shoe() -> list:
    shoe = [(rank, suit) for _ in range(HILO_DECKS) for rank in range(1, 14) for suit in range(4)]
    random.shuffle(shoe)
    return shoe


def hilo_card_text(card) -> str:
    return f"**{_HILO_RANKS[card[0] - 1]}** {_HILO_SUITS[card[1]]}"


def hilo_odds(card, shoe) -> dict:
    """Multiplicador de cada opción según las cartas que quedan (None = imposible)."""
    n = len(shoe)
    counts = {
        "higher": sum(1 for r, _ in shoe if r > card[0]),
        "lower": sum(1 for r, _ in shoe if r < card[0]),
        "same": sum(1 for r, _ in shoe if r == card[0]),
    }
    return {k: (None if c == 0 or n == 0 else max(1.01, HILO_PAYOUT_FACTOR * n / c)) for k, c in counts.items()}


def hilo_fmt_mult(mult: float) -> str:
    return f"x{mult:.2f}".rstrip("0").rstrip(".")


class HiloButton(discord.ui.Button):
    def __init__(self, kind: str, **kwargs):
        super().__init__(**kwargs)
        self.kind = kind

    async def callback(self, interaction: discord.Interaction):
        await self.view.on_press(interaction, self.kind)


class HiloView(GuildView):
    def __init__(self, user_id: str, bet: int, author_name: str = "", author_icon: str | None = None):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.bet = bet
        self.author_name = author_name
        self.author_icon = author_icon
        self.shoe = hilo_new_shoe()
        self.current = self.shoe.pop()
        self.next_card = None
        self.state = "playing"            # playing | busy | won | lost | timeout
        self.guess = None
        self.mult = 0.0
        self.profit = 0
        self.reshuffled = False
        self.message: discord.Message | None = None
        self._build()

    # ---- interfaz
    def _build(self):
        self.clear_items()
        finished = self.state in ("won", "lost", "timeout")
        if self.state in ("won", "lost"):
            self.add_item(HiloButton("again", label="Jugar otra vez", style=discord.ButtonStyle.success, row=0))
        odds = hilo_odds(self.current, self.shoe)
        for kind, emoji, word in (("higher", "⬆️", "Mayor"), ("lower", "⬇️", "Menor"), ("same", "🟰", "Igual")):
            mult = odds[kind]
            label = f"{word} ({hilo_fmt_mult(mult)})" if mult else f"{word} (—)"
            self.add_item(HiloButton(
                kind, label=label, emoji=emoji, style=discord.ButtonStyle.primary, row=0 if self.state == "playing" else 1,
                disabled=finished or self.state == "busy" or mult is None,
            ))
        self.add_item(HiloButton("help", label="Ayuda", emoji="❓", style=discord.ButtonStyle.secondary, row=2))

    def make_embed(self) -> discord.Embed:
        color = {"won": 0x2ECC71, "lost": 0xED4245, "timeout": 0x95A5A6}.get(self.state, 0x9B59B6)
        embed = discord.Embed(title="🃏 Hi-Lo", color=color)
        if self.author_name:
            embed.set_author(name=self.author_name, icon_url=self.author_icon)
        if self.state == "won":
            head = f"✅ Adivinaste **{_HILO_GUESS[self.guess]}** y ganaste **{self.profit:,}** 🪙 ({hilo_fmt_mult(self.mult)})!"
        elif self.state == "lost":
            head = f"❌ Elegiste **{_HILO_GUESS[self.guess]}** y perdiste **{self.bet:,}** 🪙."
        elif self.state == "timeout":
            head = "⏰ Se acabó el tiempo. Tu apuesta fue devuelta."
        else:
            head = f"💵 Apuesta: **{self.bet:,}** 🪙\n¿La siguiente carta será **mayor**, **menor** o **igual**?"
        embed.description = head
        embed.add_field(name="Tu carta", value=f"{hilo_card_text(self.current)}\nValor: **{self.current[0]}**", inline=False)
        if self.next_card is not None:
            embed.add_field(name="Siguiente carta",
                            value=f"{hilo_card_text(self.next_card)}\nValor: **{self.next_card[0]}**", inline=False)
        footer = f"Cartas restantes: {len(self.shoe)}"
        if self.reshuffled and self.state == "playing":
            footer += " · 🔀 mazo nuevo"
        embed.set_footer(text=footer)
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta partida no es tuya.", ephemeral=True)
            return False
        return True

    # ---- acciones
    async def on_press(self, interaction: discord.Interaction, kind: str):
        if kind == "help":
            await interaction.response.send_message(
                "**🃏 Cómo se juega Hi-Lo**\n"
                "Ves una carta (A=1, J=11, Q=12, K=13). Adivina si la siguiente será **mayor**, **menor** o **igual**.\n"
                "• Cuanto menos probable, más paga: el multiplicador sale de las cartas que quedan en el mazo.\n"
                "• Si aciertas ganas tu apuesta × multiplicador; si fallas pierdes la apuesta.\n"
                "• Si sale una carta igual y elegiste mayor o menor, pierdes.\n"
                "• Con **Jugar otra vez** repites la misma apuesta.",
                ephemeral=True)
            return
        if kind == "again":
            await self._again(interaction)
            return
        await self._guess(interaction, kind)

    async def _guess(self, interaction: discord.Interaction, kind: str):
        if self.state != "playing":
            await interaction.response.defer()
            return
        mult = hilo_odds(self.current, self.shoe)[kind]
        if mult is None:
            await interaction.response.send_message("❌ Esa opción no es posible con esta carta.", ephemeral=True)
            return
        self.state = "busy"
        nxt = self.shoe.pop()
        won = ((kind == "higher" and nxt[0] > self.current[0]) or (kind == "lower" and nxt[0] < self.current[0])
               or (kind == "same" and nxt[0] == self.current[0]))
        payout = int(self.bet * mult) if won else 0
        if won:
            await update_balance(self.user_id, payout)
        await log_bet(self.user_id, "🃏 Hi-Lo", self.bet, payout - self.bet)
        self.next_card, self.guess, self.mult = nxt, kind, mult
        self.profit = payout - self.bet
        self.state = "won" if won else "lost"
        self._build()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    async def _again(self, interaction: discord.Interaction):
        if self.state not in ("won", "lost"):
            await interaction.response.defer()
            return
        balance = await get_balance(self.user_id)
        if balance < self.bet:
            await interaction.response.send_message(
                f"❌ Necesitas **{self.bet:,}** 🪙 para jugar otra vez y tienes **{balance:,}** 🪙.", ephemeral=True)
            return
        previous = self.state
        self.state = "busy"
        try:
            await update_balance(self.user_id, -self.bet)
            await track_mission(self.user_id, "hilo_played")
        except Exception:
            self.state = previous
            raise
        self.reshuffled = len(self.shoe) < 20
        if self.reshuffled:
            self.shoe = hilo_new_shoe()
        self.current, self.next_card, self.guess = self.shoe.pop(), None, None
        self.state = "playing"
        self._build()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    async def on_timeout(self):
        refunded = self.state == "playing"
        if refunded:
            self.state = "timeout"
            await update_balance(self.user_id, self.bet)
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(embed=self.make_embed() if refunded else None, view=self)
            except discord.HTTPException:
                pass


async def hilo_create(user_id: str, username: str, bet_text: str, author_name: str = "", author_icon: str | None = None):
    """Devuelve (error, vista). Cobra la apuesta si todo está bien."""
    await get_or_create_user(user_id, username)
    balance = await get_balance(user_id)
    bet = parse_amount_or_all(bet_text, balance)
    if bet is None or bet <= 0:
        return "Escribe una apuesta válida (`all`, `5m`, `500k`...).", None
    if bet > balance:
        return f"Tienes **{balance:,}** 🪙 y quieres apostar **{bet:,}** 🪙.", None
    await update_balance(user_id, -bet)
    await track_mission(user_id, "hilo_played")
    return None, HiloView(user_id, bet, author_name, author_icon)


@tree.command(name="hilo", description="Hi-Lo: adivina si la siguiente carta es mayor, menor o igual")
@app_commands.describe(cantidad="Apuesta (acepta all, 5m, 500k)")
async def hilo_command(interaction: discord.Interaction, cantidad: str):
    error, view = await hilo_create(str(interaction.user.id), interaction.user.name, cantidad,
                                    interaction.user.display_name, interaction.user.display_avatar.url)
    if error:
        await interaction.response.send_message(embed=_err_embed("No se pudo empezar", error), ephemeral=True)
        return
    await interaction.response.send_message(embed=view.make_embed(), view=view)
    view.message = await interaction.original_response()


# =====================================================================
#  TIENDA: /añadir rol y /quitar rol  (roles propios de cada servidor)
# =====================================================================
SHOP_MAX_ITEMS = 25          # el menú desplegable de Discord admite 25 opciones
SHOP_CUSTOM_MAX_NAME = 32
SHOP_CUSTOM_MAX_DESC = 70
SHOP_PRICE_MAX = 10 ** 13


async def load_custom_items():
    """Carga en memoria los roles que los administradores añadieron a la tienda de este servidor."""
    gid = _current_guild.get()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, name, description, price, collect_bonus, collect_hours, role_id FROM custom_items ORDER BY rowid"
        ) as cur:
            rows = await cur.fetchall()
    _custom_shop[gid] = {
        item_id: {
            "name": name, "description": description, "price": price, "category": "rol",
            "collect_bonus": bonus, "collect_hours": hours, "custom": True, "discord_role_id": role_id,
        }
        for item_id, name, description, price, bonus, hours, role_id in rows
    }


def _shop_err(message: str) -> discord.Embed:
    return discord.Embed(title="❌ No se pudo", description=message, color=0xFF4444)


async def shop_add_role(
    guild: discord.Guild,
    member: discord.Member,
    role: discord.Role,
    price_text: str,
    bonus_text: str,
    hours: int,
    name: str | None = None,
    description: str | None = None,
    emoji: str | None = None,
) -> tuple[bool, discord.Embed]:
    """Añade (o actualiza) un rol de Discord como objeto de la tienda de este servidor."""
    if not member.guild_permissions.administrator:
        return False, _shop_err("Solo los administradores del servidor pueden añadir roles a la tienda.")
    if role.is_default() or role.managed:
        return False, _shop_err("No puedo vender @everyone ni roles de bots o integraciones.")
    me = guild.me
    if me is None or not me.guild_permissions.manage_roles:
        return False, _shop_err("Necesito el permiso **Gestionar roles** para entregar roles.")
    if role >= me.top_role:
        return False, _shop_err(
            f"{role.mention} está por encima (o al mismo nivel) de mi rol más alto, así que no podría entregarlo. "
            "Sube mi rol en *Ajustes del servidor → Roles*.")
    price = loan_parse_amount(str(price_text))
    bonus = loan_parse_amount(str(bonus_text))
    if price is None or not 1 <= price <= SHOP_PRICE_MAX:
        return False, _shop_err(f"El precio debe ser un número entre 1 y {SHOP_PRICE_MAX:,} (acepta `5m`, `500k`).")
    if bonus is None or not 1 <= bonus <= SHOP_PRICE_MAX:
        return False, _shop_err(f"La ganancia por collect debe ser un número entre 1 y {SHOP_PRICE_MAX:,}.")
    if not 1 <= int(hours) <= 720:
        return False, _shop_err("Las horas entre collects deben estar entre 1 y 720.")
    name = " ".join((name or role.name).split())
    if not 1 <= len(name) <= SHOP_CUSTOM_MAX_NAME:
        return False, _shop_err(f"El nombre debe tener entre 1 y {SHOP_CUSTOM_MAX_NAME} caracteres.")
    emoji = (emoji or "🎭").strip()
    if not 1 <= len(emoji) <= 8:
        return False, _shop_err("Usa un emoji normal (por ejemplo 🔥), no un emoji personalizado.")
    description = " ".join((description or "").split())
    if len(description) > SHOP_CUSTOM_MAX_DESC:
        return False, _shop_err(f"La descripción puede tener como máximo {SHOP_CUSTOM_MAX_DESC} caracteres.")

    await enter_guild(guild.id)
    gid = str(guild.id)
    custom = _custom_shop.setdefault(gid, {})
    existing_id = next((i for i, it in custom.items() if it.get("discord_role_id") == str(role.id)), None)
    full_name = f"{emoji} Rol: {name}"
    wanted = _plain(name)
    for item_id, item in SHOP_ITEMS.items():
        if item_id == existing_id:
            continue
        if wanted in (_plain(item["name"].split("Rol:", 1)[-1]), _plain(item_id)) or _plain(full_name) == _plain(item["name"]):
            return False, _shop_err(f"Ya existe un objeto llamado **{item['name']}**. Elige otro nombre.")
    if existing_id is None and len(SHOP_ITEMS) >= SHOP_MAX_ITEMS:
        return False, _shop_err(
            f"La tienda ya tiene el máximo de **{SHOP_MAX_ITEMS}** objetos (es el límite del menú de Discord). "
            "Quita alguno con `/quitar rol`.")

    if not description:
        description = f"Gana **+{bonus:,}** 🪙 cada {hours}h con `/collect`."
    else:
        description = f"{description} — **+{bonus:,}** 🪙 cada {hours}h"
    if existing_id is None:
        seq = int(await setting_get("custom_item_seq", "0") or 0) + 1
        await setting_set("custom_item_seq", str(seq))
        item_id = f"c{seq}"
    else:
        item_id = existing_id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await db.execute(
                "INSERT INTO custom_items (id, name, description, price, collect_bonus, collect_hours, role_id, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, "
                "description=excluded.description, price=excluded.price, collect_bonus=excluded.collect_bonus, "
                "collect_hours=excluded.collect_hours, role_id=excluded.role_id",
                (item_id, full_name, description, price, bonus, int(hours), str(role.id), str(member.id),
                 datetime.utcnow().isoformat()),
            )
            await db.execute(
                "INSERT INTO shop_guild_roles (guild_id, item_id, role_id) VALUES (?, ?, ?) "
                "ON CONFLICT(guild_id, item_id) DO UPDATE SET role_id=excluded.role_id",
                (gid, item_id, str(role.id)),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    custom[item_id] = {
        "name": full_name, "description": description, "price": price, "category": "rol",
        "collect_bonus": bonus, "collect_hours": int(hours), "custom": True, "discord_role_id": str(role.id),
    }
    embed = discord.Embed(title="🛒 Rol actualizado en la tienda" if existing_id else "🛒 Rol añadido a la tienda",
                          color=0x00FF88)
    embed.description = (
        f"**{full_name}** ↔ {role.mention}\n"
        f"💵 Precio: **{price:,}** 🪙\n"
        f"💰 Gana **{bonus:,}** 🪙 cada **{int(hours)}h** con `/collect`\n"
        f"🆔 ID: `{item_id}`\n\n"
        "Los jugadores lo compran con `/buy` y reclaman el rol de Discord con `/use`."
    )
    embed.set_footer(text=f"Objetos en la tienda: {len(SHOP_ITEMS)}/{SHOP_MAX_ITEMS}")
    return True, embed


async def shop_remove_role(guild: discord.Guild, member: discord.Member, text: str) -> tuple[bool, discord.Embed]:
    if not member.guild_permissions.administrator:
        return False, _shop_err("Solo los administradores del servidor pueden quitar roles de la tienda.")
    await enter_guild(guild.id)
    gid = str(guild.id)
    custom = _custom_shop.get(gid, {})
    item_id = resolve_shop_item(text)
    if item_id not in custom:
        return False, _shop_err("Solo se pueden quitar los roles que se añadieron con `/añadir rol`.")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            async with db.execute(
                "SELECT COUNT(*) FROM inventory WHERE item_id=? AND quantity > 0", (item_id,)
            ) as cur:
                owners = (await cur.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM role_loans WHERE item_id=?", (item_id,)) as cur:
                loans = (await cur.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM role_listings WHERE item_id=?", (item_id,)) as cur:
                listings = (await cur.fetchone())[0]
            if owners or loans or listings:
                await db.rollback()
                return False, _shop_err(
                    f"No se puede quitar: **{owners}** jugador(es) lo tienen, **{loans}** préstamo(s) activo(s) y "
                    f"**{listings}** anuncio(s) en el mercado. Solo se pueden quitar roles que nadie tenga.")
            await db.execute("DELETE FROM custom_items WHERE id=?", (item_id,))
            await db.execute("DELETE FROM shop_guild_roles WHERE guild_id=? AND item_id=?", (gid, item_id))
            await db.execute("DELETE FROM role_collects WHERE item_id=?", (item_id,))
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    removed = custom.pop(item_id)
    return True, discord.Embed(title="🗑️ Rol quitado de la tienda", color=0x00FF88,
                               description=f"**{removed['name']}** ya no está en la tienda.")


async def custom_item_autocomplete(interaction: discord.Interaction, current: str):
    t = _plain(current)
    gid = str(interaction.guild_id)
    choices = []
    for item_id, item in _custom_shop.get(gid, {}).items():
        if t and t not in _plain(item["name"]):
            continue
        choices.append(app_commands.Choice(name=f"{item['name']} · {item['price']:,} 🪙"[:100], value=item_id))
    return choices[:25]


anadir_group = app_commands.Group(
    name="añadir", description="Añade objetos a la tienda de este servidor", guild_only=True,
    default_permissions=discord.Permissions(administrator=True),
)
quitar_group = app_commands.Group(
    name="quitar", description="Quita objetos de la tienda de este servidor", guild_only=True,
    default_permissions=discord.Permissions(administrator=True),
)
tree.add_command(anadir_group)
tree.add_command(quitar_group)


@anadir_group.command(name="rol", description="Añade un rol de Discord a la tienda (si ya estaba, lo actualiza)")
@app_commands.describe(
    rol="Rol de Discord que se entregará a quien lo compre",
    precio="Precio en monedas (acepta 5m, 500k)",
    ganancia="Monedas que paga cada /collect (acepta 5m, 500k)",
    horas="Cada cuántas horas se puede cobrar (1-720)",
    nombre="Nombre en la tienda (por defecto, el nombre del rol)",
    descripcion="Descripción corta (opcional)",
    emoji="Emoji del objeto (por defecto 🎭)",
)
async def anadir_rol_command(
    interaction: discord.Interaction,
    rol: discord.Role,
    precio: str,
    ganancia: str,
    horas: app_commands.Range[int, 1, 720],
    nombre: _Optional[str] = None,
    descripcion: _Optional[str] = None,
    emoji: _Optional[str] = None,
):
    ok, embed = await shop_add_role(interaction.guild, interaction.user, rol, precio, ganancia, horas,
                                    nombre, descripcion, emoji)
    await interaction.response.send_message(embed=embed, ephemeral=not ok)


@quitar_group.command(name="rol", description="Quita de la tienda un rol que añadiste (solo si nadie lo tiene)")
@app_commands.describe(rol="Rol de la tienda que quieres quitar")
async def quitar_rol_command(interaction: discord.Interaction, rol: str):
    ok, embed = await shop_remove_role(interaction.guild, interaction.user, rol)
    await interaction.response.send_message(embed=embed, ephemeral=not ok)


quitar_rol_command.autocomplete("rol")(custom_item_autocomplete)


async def shop_handle_prefix(message: discord.Message, cmd: str, args: list) -> bool:
    """,añadir rol @rol <precio> <ganancia> <horas> [nombre]   ·   ,quitar rol <nombre>"""
    if cmd not in ("añadir", "anadir", "quitar") or not args or args[0].lower() not in ("rol", "role"):
        return False
    if cmd == "quitar":
        if len(args) < 2:
            await message.channel.send("❌ Uso: `,quitar rol <nombre o ID>`")
            return True
        ok, embed = await shop_remove_role(message.guild, message.author, " ".join(args[1:]))
        await message.channel.send(embed=embed)
        return True
    usage = "❌ Uso: `,añadir rol @rol <precio> <ganancia> <horas> [nombre]` — ej: `,añadir rol @VIP 5m 100k 12 Súper VIP`"
    rest = [a for a in args[1:] if not re.fullmatch(r"<@&\d+>", a)]
    if not message.role_mentions or len(rest) < 3 or not rest[2].isdigit():
        await message.channel.send(usage)
        return True
    ok, embed = await shop_add_role(message.guild, message.author, message.role_mentions[0], rest[0], rest[1],
                                    int(rest[2]), " ".join(rest[3:]) or None)
    await message.channel.send(embed=embed)
    return True


# =====================================================================
#  PANEL WEB (dashboard) para configurar el bot, estilo UnbelievaBoat
#  - Corre dentro del mismo proceso del bot (aiohttp).
#  - Todo lo configurable vive en la base de datos (tabla bot_settings).
#  - Login con Discord (OAuth2) y/o con contraseña. Ver variables DASHBOARD_*.
# =====================================================================
import json as _json
import hmac as _hmac
import hashlib as _hashlib
import base64 as _b64
import secrets as _secrets
import time as _time
from urllib.parse import urlencode as _urlencode
import aiohttp as _aiohttp
from aiohttp import web as _web

# ---- valores que antes estaban fijos en el codigo y ahora se editan desde el panel
WORK_MIN, WORK_MAX, WORK_COOLDOWN_SECONDS = 1_000, 100_000, 30
SLUT_MIN, SLUT_MAX, SLUT_COOLDOWN_SECONDS, SLUT_CHANCE = 1_000, 100_000, 30, 60
SLUT_FINE_MIN, SLUT_FINE_MAX = 1_000, 100_000
CRIME_MIN, CRIME_MAX, CRIME_COOLDOWN_SECONDS, CRIME_CHANCE = 1_000, 100_000, 30, 60
CRIME_FINE_MIN, CRIME_FINE_MAX = 1_000, 100_000
ROB_COOLDOWN_MINUTES = 60
ROB_SUCCESS_CHANCE = 40
ROB_STEAL_MIN_PCT, ROB_STEAL_MAX_PCT = 10, 40
ROB_FINE_PCT = 10
DAILY_FIRST_REWARD = 5_000       # dia 1 de racha
DAILY_BASE_REWARD = 50_000       # dia 2 de racha
DAILY_STREAK_STEP = 10_000       # lo que sube cada dia extra (hasta el dia 30)
LOAN_PERIOD_DAYS = 7
WEEKLY_PRIZE_1, WEEKLY_PRIZE_2, WEEKLY_PRIZE_3 = WEEKLY_PRIZES

_MONEY_MAX = 10 ** 13


def _f(key, label, typ="int", lo=0, hi=_MONEY_MAX, unit="", help="", step=None, sub=None):
    field = {"key": key, "label": label, "type": typ, "min": lo, "max": hi, "unit": unit, "help": help}
    if step is not None:
        field["step"] = step
    if sub:
        field["sub"] = sub
    return field


CONFIG_GROUPS_STATIC = [
    {"id": "work", "icon": "💼", "title": "Work", "desc": "Comando /work y ,work: trabajo seguro que siempre paga.", "fields": [
        _f("WORK_MIN", "Ganancia mínima", unit="🪙", help="Lo menos que puede pagar un trabajo."),
        _f("WORK_MAX", "Ganancia máxima", unit="🪙", help="Lo más que puede pagar un trabajo."),
        _f("WORK_COOLDOWN_SECONDS", "Cooldown", hi=604800, unit="seg", help="Tiempo de espera entre trabajos."),
    ]},
    {"id": "slut", "icon": "💋", "title": "Slut", "desc": "Comando /slut y ,slut: arriesgado, puede dar multa.", "fields": [
        _f("SLUT_MIN", "Ganancia mínima", unit="🪙"),
        _f("SLUT_MAX", "Ganancia máxima", unit="🪙"),
        _f("SLUT_CHANCE", "Probabilidad de éxito", hi=100, unit="%", help="Si falla, paga multa."),
        _f("SLUT_FINE_MIN", "Multa mínima", unit="🪙", help="Nunca se cobra más de lo que el usuario tiene en la cartera."),
        _f("SLUT_FINE_MAX", "Multa máxima", unit="🪙"),
        _f("SLUT_COOLDOWN_SECONDS", "Cooldown", hi=604800, unit="seg"),
    ]},
    {"id": "crime", "icon": "🦹", "title": "Crime", "desc": "Comando /crime y ,crime: más riesgo, más historias.", "fields": [
        _f("CRIME_MIN", "Ganancia mínima", unit="🪙"),
        _f("CRIME_MAX", "Ganancia máxima", unit="🪙"),
        _f("CRIME_CHANCE", "Probabilidad de éxito", hi=100, unit="%"),
        _f("CRIME_FINE_MIN", "Multa mínima", unit="🪙"),
        _f("CRIME_FINE_MAX", "Multa máxima", unit="🪙"),
        _f("CRIME_COOLDOWN_SECONDS", "Cooldown", hi=604800, unit="seg"),
    ]},
    {"id": "rob", "icon": "🥷", "title": "Robos", "desc": "Comando /rob: robarle monedas de la cartera a otro jugador.", "fields": [
        _f("ROB_SUCCESS_CHANCE", "Probabilidad de éxito", hi=100, unit="%"),
        _f("ROB_STEAL_MIN_PCT", "Mínimo robado", hi=100, unit="% de la cartera", help="Porcentaje de la cartera de la víctima."),
        _f("ROB_STEAL_MAX_PCT", "Máximo robado", hi=100, unit="% de la cartera"),
        _f("ROB_FINE_PCT", "Multa al fallar", hi=100, unit="% de la cartera de la víctima"),
        _f("ROB_COOLDOWN_MINUTES", "Cooldown", hi=10080, unit="min"),
    ]},
    {"id": "jail", "icon": "🔒", "title": "Cárcel", "desc": "Qué pasa cuando te atrapan robando.", "fields": [
        _f("JAIL_BASE_MINUTES", "Condena base", hi=1440, unit="min", help="Minutos de cárcel la primera vez."),
        _f("JAIL_EXTRA_MINUTES_PER_STRIKE", "Extra por reincidencia", hi=1440, unit="min", help="Se suma por cada captura seguida."),
        _f("JAIL_MAX_MINUTES", "Condena máxima", hi=10080, unit="min"),
        _f("JAIL_STRIKE_RESET_HOURS", "Reinicio de reincidencia", hi=720, unit="horas", help="Sin caer en este tiempo, vuelve a la condena base."),
        _f("JAIL_BAIL_PER_MINUTE", "Fianza por minuto", unit="🪙", help="Costo de /fianza = minutos restantes × este valor."),
    ]},
    {"id": "daily", "icon": "🎁", "title": "Diario", "desc": "Recompensa de /daily con racha de hasta 30 días.", "fields": [
        _f("DAILY_FIRST_REWARD", "Día 1", unit="🪙"),
        _f("DAILY_BASE_REWARD", "Día 2", unit="🪙"),
        _f("DAILY_STREAK_STEP", "Aumento por cada día extra", unit="🪙", help="Día N = día 2 + (N-2) × este valor."),
    ]},
    {"id": "loans", "icon": "🏦", "title": "Préstamos", "desc": "El banco del casino (/loan, /debt, /payloan).", "fields": [
        _f("LOAN_MIN", "Préstamo mínimo", unit="🪙"),
        _f("LOAN_MAX", "Préstamo máximo", unit="🪙"),
        _f("LOAN_INTEREST_PERCENT", "Interés por tramo", hi=1000, unit="%", help="Se suma este % por cada tramo de monto prestado."),
        _f("LOAN_TIER_SIZE", "Tamaño del tramo", lo=1, unit="🪙"),
        _f("LOAN_WEEKLY_PERCENT", "Cuota", lo=1, hi=100, unit="% de la deuda", help="Porcentaje de la deuda que se paga en cada cuota."),
        _f("LOAN_LATE_FEE_PERCENT", "Recargo por atraso", hi=100, unit="%"),
        _f("LOAN_PERIOD_DAYS", "Cada cuánto se cobra", lo=1, hi=60, unit="días"),
    ]},
    {"id": "roles", "icon": "🤝", "title": "Roles prestados", "desc": "Préstamo y mercado de roles.", "fields": [
        _f("ROLE_LOAN_LENDER_PERCENT", "% del collect para el dueño", hi=100, unit="%", help="En /prestar, parte de cada collect que va al dueño del rol."),
        _f("ROLE_MARKET_FEE_PERCENT", "Comisión del mercado", hi=100, unit="%", help="Se descuenta al vendedor en ventas y alquileres."),
    ]},
    {"id": "events", "icon": "🎉", "title": "Eventos", "desc": "Collect doble. Para activar uno ahora mismo usa el Resumen.", "fields": [
        _f("WEEKEND_DOUBLE_COLLECT", "Collect doble los fines de semana", typ="bool", help="Sábado y domingo (hora UTC)."),
        _f("COLLECT_EVENT_MULTIPLIER", "Multiplicador del fin de semana", lo=1, hi=10, unit="×", help="Solo el evento automático de sábado y domingo (por defecto ×2). Los eventos manuales de /evento llegan hasta ×50."),
    ]},
    {"id": "weekly", "icon": "🏆", "title": "Ranking semanal", "desc": "Premios automáticos de /top cada lunes 00:00 UTC.", "fields": [
        _f("WEEKLY_PRIZE_1", "Premio 1º lugar", unit="🪙"),
        _f("WEEKLY_PRIZE_2", "Premio 2º lugar", unit="🪙"),
        _f("WEEKLY_PRIZE_3", "Premio 3º lugar", unit="🪙"),
    ]},
    {"id": "clans", "icon": "🛡️", "title": "Clanes", "desc": "Banco compartido y equipos.", "fields": [
        _f("CLAN_CREATE_COST", "Costo de crear un clan", unit="🪙"),
        _f("CLAN_MAX_MEMBERS", "Máximo de miembros", lo=2, hi=50),
    ]},
    {"id": "games", "icon": "🎰", "title": "Juegos", "desc": "Mines y torneos de luchadores.", "fields": [
        _f("MINES_PAYOUT_FACTOR", "Pago de Mines", typ="float", lo=0.5, hi=1.0, step=0.01, unit="× justo", help="1.00 = sin ventaja de la casa. 0.96 = 4% de ventaja."),
        _f("HILO_PAYOUT_FACTOR", "Pago de Hi-Lo", typ="float", lo=0.5, hi=1.0, step=0.01, unit="× justo", help="1.00 = sin ventaja de la casa. 0.97 = 3% de ventaja."),
        _f("FIGHTER_TOURNAMENT_PRIZE", "Premio del torneo sin apuesta", unit="🪙"),
        _f("FIGHTER_TOURNAMENT_RAKE_PERCENT", "Comisión del torneo con apuesta", hi=100, unit="%"),
    ]},
]
CONFIG_PAIRS = [
    ("WORK_MIN", "WORK_MAX"), ("SLUT_MIN", "SLUT_MAX"), ("SLUT_FINE_MIN", "SLUT_FINE_MAX"),
    ("CRIME_MIN", "CRIME_MAX"), ("CRIME_FINE_MIN", "CRIME_FINE_MAX"), ("ROB_STEAL_MIN_PCT", "ROB_STEAL_MAX_PCT"),
    ("LOAN_MIN", "LOAN_MAX"),
]
ITEM_DEFAULTS: dict = {}
for _iid, _item in _BASE_SHOP_ITEMS.items():
    ITEM_DEFAULTS[f"ITEM:{_iid}:price"] = _item["price"]
    if _item["category"] == "rol":
        ITEM_DEFAULTS[f"ITEM:{_iid}:collect_bonus"] = _item["collect_bonus"]
        ITEM_DEFAULTS[f"ITEM:{_iid}:collect_hours"] = _item["collect_hours"]
for _fid, _fighter in FIGHTERS.items():
    ITEM_DEFAULTS[f"FIGHTER:{_fid}:price"] = _fighter["price"]
CONFIG_DEFAULTS_STATIC = {
    field["key"]: globals()[field["key"]] for g in CONFIG_GROUPS_STATIC for field in g["fields"]
}


def config_groups() -> list[dict]:
    """Esquema completo (grupos estaticos + tienda y luchadores generados desde los datos reales)."""
    shop_fields = []
    for item_id, item in _BASE_SHOP_ITEMS.items():
        shop_fields.append(_f(f"ITEM:{item_id}:price", "Precio", unit="🪙", sub=item["name"]))
        if item["category"] == "rol":
            shop_fields.append(_f(f"ITEM:{item_id}:collect_bonus", "Ganancia por /collect", unit="🪙", sub=item["name"]))
            shop_fields.append(_f(f"ITEM:{item_id}:collect_hours", "Cada cuántas horas", lo=1, hi=720, unit="horas", sub=item["name"]))
    fighter_fields = [_f(f"FIGHTER:{fid}:price", "Precio", unit="🪙", sub=f["name"]) for fid, f in FIGHTERS.items()]
    return CONFIG_GROUPS_STATIC + [
        {"id": "shop", "icon": "🛒", "title": "Tienda y roles", "desc": "Precio de cada objeto y lo que pagan los roles con /collect.", "fields": shop_fields},
        {"id": "fighters", "icon": "🥊", "title": "Luchadores", "desc": "Precio de cada luchador.", "fields": fighter_fields},
    ]


def config_field_map() -> dict:
    return {f["key"]: f for g in config_groups() for f in g["fields"]}


def config_default(key: str):
    return CONFIG_DEFAULTS_STATIC[key] if key in CONFIG_DEFAULTS_STATIC else ITEM_DEFAULTS[key]


def config_current(key: str):
    if key.startswith("ITEM:"):
        _, item_id, field = key.split(":")
        return SHOP_ITEMS[item_id][field]
    if key.startswith("FIGHTER:"):
        _, fighter_id, field = key.split(":")
        return FIGHTERS[fighter_id][field]
    return globals()[key]


def _config_set_raw(key: str, value):
    if key.startswith("ITEM:"):
        _, item_id, field = key.split(":")
        SHOP_ITEMS[item_id][field] = value
    elif key.startswith("FIGHTER:"):
        _, fighter_id, field = key.split(":")
        FIGHTERS[fighter_id][field] = value
    else:
        globals()[key] = value


_ROLE_DESC_RE = re.compile(r"Gana \*\*\+[\d,]+\*\* 🪙 cada \d+h con `/collect`\.")


def _config_post_apply():
    """Recalcula lo que se deriva de varios valores (premios, periodo de prestamos, textos de roles)."""
    globals()["WEEKLY_PRIZES"] = (WEEKLY_PRIZE_1, WEEKLY_PRIZE_2, WEEKLY_PRIZE_3)
    globals()["LOAN_PERIOD"] = timedelta(days=LOAN_PERIOD_DAYS)
    for item in _BASE_SHOP_ITEMS.values():
        if item["category"] == "rol" and _ROLE_DESC_RE.fullmatch(item.get("description", "")):
            item["description"] = (
                f"Gana **+{item['collect_bonus']:,}** 🪙 cada {item['collect_hours']}h con `/collect`."
            )


def config_validate(updates: dict) -> tuple[dict, list[str]]:
    """Valida los cambios pedidos. Devuelve (valores limpios, lista de errores)."""
    fields = config_field_map()
    clean: dict = {}
    errors: list[str] = []
    for key, raw in updates.items():
        field = fields.get(key)
        if field is None:
            errors.append(f"Ajuste desconocido: {key}")
            continue
        label = f"{field.get('sub') + ' · ' if field.get('sub') else ''}{field['label']}"
        typ = field["type"]
        if typ == "bool":
            if not isinstance(raw, bool):
                errors.append(f"{label}: debe ser sí/no.")
                continue
            clean[key] = raw
            continue
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            errors.append(f"{label}: debe ser un número.")
            continue
        if typ == "int":
            if isinstance(raw, float) and not raw.is_integer():
                errors.append(f"{label}: debe ser un número entero.")
                continue
            value = int(raw)
        else:
            value = round(float(raw), 4)
        if not field["min"] <= value <= field["max"]:
            errors.append(f"{label}: debe estar entre {field['min']:,} y {field['max']:,}.")
            continue
        clean[key] = value
    if not errors:
        merged = lambda k: clean[k] if k in clean else config_current(k)  # noqa: E731
        for low, high in CONFIG_PAIRS:
            if (low in clean or high in clean) and merged(low) > merged(high):
                lf, hf = fields[low], fields[high]
                errors.append(f"{lf['label']} no puede ser mayor que {hf['label'].lower()} (revisa el grupo).")
    return clean, errors


def config_apply(clean: dict):
    for key, value in clean.items():
        _config_set_raw(key, value)
    _config_post_apply()


async def init_dashboard_tables():
    async with aiosqlite.connect(GLOBAL_DB_PATH) as db:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS config_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, user_id TEXT NOT NULL,
                user_name TEXT NOT NULL, key TEXT NOT NULL, old TEXT, new TEXT)"""
        )
        await db.commit()


async def config_load():
    """Lee los ajustes guardados y los aplica (al arrancar el bot)."""
    async with aiosqlite.connect(GLOBAL_DB_PATH) as db:
        async with db.execute("SELECT key, value FROM bot_settings WHERE key LIKE 'cfg:%'") as cur:
            rows = await cur.fetchall()
    saved: dict = {}
    for key, value in rows:
        try:
            saved[key[4:]] = _json.loads(value)
        except ValueError:
            continue
    # cada valor se valida por separado: uno roto no tumba al resto
    for key, value in saved.items():
        clean, errors = config_validate({key: value})
        if not errors:
            config_apply(clean)
    _config_post_apply()


async def config_save(updates: dict, user_id: str, user_name: str) -> tuple[dict, list[str]]:
    clean, errors = config_validate(updates)
    if errors:
        return {}, errors
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(GLOBAL_DB_PATH) as db:
        for key, value in clean.items():
            old = config_current(key)
            if value == config_default(key):
                await db.execute("DELETE FROM bot_settings WHERE key=?", (f"cfg:{key}",))
            else:
                await db.execute(
                    "INSERT INTO bot_settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (f"cfg:{key}", _json.dumps(value)),
                )
            if old != value:
                await db.execute(
                    "INSERT INTO config_audit (ts, user_id, user_name, key, old, new) VALUES (?, ?, ?, ?, ?, ?)",
                    (now, user_id, user_name, key, _json.dumps(old), _json.dumps(value)),
                )
        await db.commit()
    config_apply(clean)
    return clean, []


def config_snapshot() -> list[dict]:
    """Esquema + valor actual + valor por defecto, listo para enviarlo al panel."""
    out = []
    for group in config_groups():
        fields = []
        for field in group["fields"]:
            item = dict(field)
            item["value"] = config_current(field["key"])
            item["default"] = config_default(field["key"])
            fields.append(item)
        out.append({"id": group["id"], "icon": group["icon"], "title": group["title"],
                    "desc": group["desc"], "fields": fields})
    return out


async def dashboard_stats() -> dict:
    totals = {"users": 0, "money_wallet": 0, "money_bank": 0, "clans": 0, "loans": 0, "role_loans": 0, "listings": 0}
    per_guild, manual_events, event_text = [], 0, None
    for guild in list(client.guilds):
        try:
            await enter_guild(guild.id)
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT COUNT(*), COALESCE(SUM(balance),0), COALESCE(SUM(bank),0) FROM users"
                ) as cur:
                    users, wallet, bank = await cur.fetchone()
                counts = {}
                for name, sql in (
                    ("clans", "SELECT COUNT(*) FROM clans"),
                    ("loans", "SELECT COUNT(*) FROM loans"),
                    ("role_loans", "SELECT COUNT(*) FROM role_loans"),
                    ("listings", "SELECT COUNT(*) FROM role_listings"),
                ):
                    try:
                        async with db.execute(sql) as cur:
                            counts[name] = (await cur.fetchone())[0]
                    except Exception:
                        counts[name] = 0
            mult, text = await collect_event_info()
            if await manual_collect_event_active():
                manual_events += 1
        except Exception as exc:
            print(f"Estadísticas: no pude leer el servidor {guild.id}: {exc}")
            continue
        totals["users"] += users
        totals["money_wallet"] += wallet
        totals["money_bank"] += bank
        for key, value in counts.items():
            totals[key] += value
        per_guild.append({"id": str(guild.id), "name": guild.name, "users": users,
                          "money": wallet + bank, "event_multiplier": mult})
        event_text = event_text or text
    event_text = event_text or "No hay servidores."
    if manual_events:
        event_text += f"\n🎛️ Evento manual activo en {manual_events} servidor(es)."
    return {**totals, "guilds": len(client.guilds), "per_guild": per_guild,
            "event_multiplier": max([g["event_multiplier"] for g in per_guild] or [1]), "event_text": event_text}



async def dashboard_audit(limit: int = 40) -> list[dict]:
    fields = config_field_map()
    async with aiosqlite.connect(GLOBAL_DB_PATH) as db:
        async with db.execute(
            "SELECT ts, user_name, key, old, new FROM config_audit ORDER BY id DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
    out = []
    for ts, user_name, key, old, new in rows:
        field = fields.get(key)
        label = key if field is None else f"{field.get('sub') + ' · ' if field.get('sub') else ''}{field['label']}"
        out.append({"ts": ts, "user": user_name, "label": label, "old": old, "new": new})
    return out


async def dashboard_set_event(hours: int, multiplier: int | None = None) -> str:
    """Activa o termina el evento manual en TODOS los servidores."""
    multiplier = int(multiplier) if multiplier else _configured_collect_multiplier()
    until = datetime.utcnow() + timedelta(hours=hours)

    async def _apply():
        if hours <= 0:
            await cancel_manual_collect_event()
        else:
            await save_manual_collect_event(multiplier, until)

    await for_each_guild(_apply)
    if hours <= 0:
        return "Evento manual terminado en todos los servidores."
    return f"Collect x{multiplier} activado por {hours} h en todos los servidores."



# ------------------------------------------------------------------ /work /slut /crime (config desde el panel)
def _fmt_secs(seconds: int) -> str:
    seconds = max(0, int(seconds))
    if seconds >= 3600:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    if seconds >= 60:
        return f"{seconds // 60}m {seconds % 60}s"
    return f"{seconds}s"


async def run_income_command(kind: str, user_id: str, username: str) -> discord.Embed:
    """Ejecuta work / slut / crime usando los valores configurados en el panel."""
    await get_or_create_user(user_id, username)
    cooldown, col = {
        "work": (WORK_COOLDOWN_SECONDS, "last_work"),
        "slut": (SLUT_COOLDOWN_SECONDS, "last_slut"),
        "crime": (CRIME_COOLDOWN_SECONDS, "last_crime"),
    }[kind]
    now = datetime.utcnow()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            f"UPDATE users SET {col}=? WHERE user_id=? AND ({col} IS NULL OR {col} <= ?)",
            (now.isoformat(), user_id, (now - timedelta(seconds=cooldown)).isoformat()),
        )
        await db.commit()
        if cur.rowcount == 0:
            async with db.execute(f"SELECT {col} FROM users WHERE user_id=?", (user_id,)) as c2:
                row = await c2.fetchone()
            left = cooldown
            if row and row[0]:
                left = cooldown - (now - datetime.fromisoformat(row[0])).total_seconds()
            if kind == "work":
                return discord.Embed(title="⏰ Aún estás trabajando", color=0xFF4444,
                                     description=f"Descansa **{_fmt_secs(left)}** antes de volver a trabajar.")
            return discord.Embed(title="⏰ Cooldown Activo", color=0xFF4444,
                                 description=f"Espera **{_fmt_secs(left)}** para volver a intentarlo.")

    if kind == "work":
        earned = random.randint(WORK_MIN, max(WORK_MIN, WORK_MAX))
        titulo, desc = random.choice([
            ("👨‍🍳 Cocinero", f"Preparaste platos toda la noche y ganaste **{earned:,}** 🪙."),
            ("🚗 Taxista", f"Llevaste pasajeros por toda la ciudad y ganaste **{earned:,}** 🪙."),
            ("💻 Programador", f"Terminaste un proyecto freelance y ganaste **{earned:,}** 🪙."),
            ("🎸 Músico", f"Tocaste en una plaza y la gente aplaudió. Ganaste **{earned:,}** 🪙."),
            ("📦 Repartidor", f"Repartiste 30 pedidos y ganaste **{earned:,}** 🪙."),
            ("🧹 Limpiador", f"Limpiaste el casino de arriba a abajo. Ganaste **{earned:,}** 🪙."),
        ])
        await update_balance(user_id, earned)
        new_bal = await get_balance(user_id)
        return discord.Embed(title=f"💼 {titulo}", color=0x00FF88,
                             description=f"{desc}\n\n👛 Saldo actual: **{new_bal:,}** 🪙")

    chance, lo, hi, fine_lo, fine_hi = (
        (SLUT_CHANCE, SLUT_MIN, SLUT_MAX, SLUT_FINE_MIN, SLUT_FINE_MAX) if kind == "slut"
        else (CRIME_CHANCE, CRIME_MIN, CRIME_MAX, CRIME_FINE_MIN, CRIME_FINE_MAX)
    )
    if random.random() < chance / 100:
        earned = random.randint(lo, max(lo, hi))
        if kind == "slut":
            text = random.choice([
                f"💋 Una noche rentable. Ganaste **{earned:,}** 🪙.",
                f"💄 El cliente quedó satisfecho. Ganaste **{earned:,}** 🪙.",
                f"🌹 Noche de buenas propinas. Ganaste **{earned:,}** 🪙.",
            ])
            title, color = "💋 ¡Éxito!", 0xFF69B4
        else:
            text = random.choice([
                f"🏦 Asaltaste un banco pequeño y escapaste con **{earned:,}** 🪙.",
                f"💎 Vendiste joyas robadas en el mercado negro. Ganaste **{earned:,}** 🪙.",
                f"🎰 Hackeaste una slot machine. Ganaste **{earned:,}** 🪙.",
                f"🚗 Robaste un auto de lujo y lo vendiste. Ganaste **{earned:,}** 🪙.",
                f"📱 Estafaste a un coleccionista con NFTs falsos. Ganaste **{earned:,}** 🪙.",
            ])
            title, color = "🦹 ¡Crimen Exitoso!", 0x9B59B6
        await update_balance(user_id, earned)
        new_bal = await get_balance(user_id)
        return discord.Embed(title=title, color=color, description=f"{text}\n\n👛 Saldo: **{new_bal:,}** 🪙")

    lost = min(random.randint(fine_lo, max(fine_lo, fine_hi)), await get_balance(user_id))
    await update_balance(user_id, -lost)
    new_bal = await get_balance(user_id)
    if kind == "slut":
        text, title = f"La policía te arrestó. Multa: **{lost:,}** 🪙.", "🚔 ¡Te Pillaron!"
    else:
        text = random.choice([
            f"🚔 La policía te atrapó en pleno acto. Multa: **{lost:,}** 🪙.",
            f"😬 Tu cómplice te traicionó. Perdiste **{lost:,}** 🪙 en sobornos.",
            f"🔒 Las cámaras te grabaron. Multa judicial: **{lost:,}** 🪙.",
        ])
        title = "🚔 ¡Operación Fallida!"
    return discord.Embed(title=title, color=0xFF4444, description=f"{text}\n\n👛 Saldo: **{new_bal:,}** 🪙")


@tree.command(name="work", description="Trabaja para ganar monedas")
async def work_command(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=await run_income_command("work", str(interaction.user.id), interaction.user.name))


@tree.command(name="slut", description="Arriesga para ganar monedas (puede salir mal)")
async def slut_command(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=await run_income_command("slut", str(interaction.user.id), interaction.user.name))


@tree.command(name="crime", description="Comete un crimen: gana monedas o paga una multa")
async def crime_command(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=await run_income_command("crime", str(interaction.user.id), interaction.user.name))


# ------------------------------------------------------------------ servidor web
DASH_SESSION_HOURS = 12
_login_attempts: dict = {}     # ip -> (intentos, inicio)  (limite para el login con contraseña)


def _dash_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _dash_secret() -> bytes:
    secret = _dash_env("DASHBOARD_SECRET") or (TOKEN or "dashboard") + "|dashboard-v1"
    return _hashlib.sha256(secret.encode()).digest()


def _dash_admin_ids() -> set[str]:
    return {x for x in re.split(r"[\s,;]+", _dash_env("DASHBOARD_ADMIN_IDS")) if x}


def _dash_oauth_ready() -> bool:
    return bool(_dash_env("DASHBOARD_CLIENT_SECRET"))


def _dash_password_ready() -> bool:
    return bool(_dash_env("DASHBOARD_PASSWORD"))


def dash_sign(payload: dict) -> str:
    raw = _b64.urlsafe_b64encode(_json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = _hmac.new(_dash_secret(), raw.encode(), _hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def dash_unsign(token: str | None) -> dict | None:
    if not token or "." not in token:
        return None
    raw, sig = token.rsplit(".", 1)
    expected = _hmac.new(_dash_secret(), raw.encode(), _hashlib.sha256).hexdigest()
    if not _hmac.compare_digest(sig, expected):
        return None
    try:
        data = _json.loads(_b64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("exp", 0) < _time.time():
        return None
    return data


def dash_user_allowed(user_id: str, guilds: list[dict]) -> bool:
    """Con DASHBOARD_ADMIN_IDS: solo esos usuarios. Sin ella: administradores de un servidor donde esta el bot."""
    admins = _dash_admin_ids()
    if admins:
        return user_id in admins
    bot_guilds = {str(g.id) for g in client.guilds}
    for g in guilds:
        if str(g.get("id")) in bot_guilds and (g.get("owner") or int(g.get("permissions") or 0) & 0x8):
            return True
    return False


def _dash_base_url(request) -> str:
    base = _dash_env("DASHBOARD_URL")
    if base:
        return base.rstrip("/")
    proto = request.headers.get("X-Forwarded-Proto", "http")
    host = request.headers.get("X-Forwarded-Host") or request.host
    return f"{proto}://{host}"


def _dash_session(request) -> dict | None:
    return dash_unsign(request.cookies.get("dash_session"))


def _dash_start_session(response, request, user_id: str, name: str):
    token = dash_sign({"uid": user_id, "name": name, "exp": _time.time() + DASH_SESSION_HOURS * 3600})
    response.set_cookie("dash_session", token, max_age=DASH_SESSION_HOURS * 3600, httponly=True,
                        samesite="Lax", secure=_dash_base_url(request).startswith("https"), path="/")


def _json_error(message: str, status: int):
    return _web.json_response({"ok": False, "error": message}, status=status)


async def _dash_guard(request, write: bool = False):
    """Devuelve (sesion, None) o (None, respuesta de error)."""
    session = _dash_session(request)
    if not session:
        return None, _json_error("Sesión no iniciada.", 401)
    if write and request.headers.get("X-Requested-With") != "dashboard":
        return None, _json_error("Petición no válida.", 403)   # anti-CSRF
    return session, None


async def h_index(request):
    return _web.Response(text=DASHBOARD_HTML, content_type="text/html", charset="utf-8",
                         headers={"Cache-Control": "no-store"})


async def h_health(request):
    return _web.Response(text="ok")


async def h_me(request):
    session = _dash_session(request)
    return _web.json_response({
        "authenticated": bool(session),
        "user": {"id": session["uid"], "name": session["name"]} if session else None,
        "discord": _dash_oauth_ready(),
        "password": _dash_password_ready(),
    })


async def h_login(request):
    if not _dash_oauth_ready():
        raise _web.HTTPFound("/?error=oauth")
    client_id = _dash_env("DASHBOARD_CLIENT_ID") or str(client.user.id)
    state = _secrets.token_urlsafe(24)
    url = "https://discord.com/oauth2/authorize?" + _urlencode({
        "client_id": client_id, "response_type": "code", "scope": "identify guilds", "state": state,
        "redirect_uri": _dash_base_url(request) + "/callback", "prompt": "none",
    })
    response = _web.HTTPFound(url)
    response.set_cookie("dash_state", dash_sign({"s": state, "exp": _time.time() + 600}), max_age=600,
                        httponly=True, samesite="Lax", secure=_dash_base_url(request).startswith("https"), path="/")
    raise response


async def h_callback(request):
    state_cookie = dash_unsign(request.cookies.get("dash_state"))
    if request.query.get("error") or not state_cookie or state_cookie.get("s") != request.query.get("state"):
        raise _web.HTTPFound("/?error=state")
    code = request.query.get("code")
    if not code or not _dash_oauth_ready():
        raise _web.HTTPFound("/?error=oauth")
    client_id = _dash_env("DASHBOARD_CLIENT_ID") or str(client.user.id)
    redirect_uri = _dash_base_url(request) + "/callback"
    try:
        async with _aiohttp.ClientSession(timeout=_aiohttp.ClientTimeout(total=15)) as http:
            async with http.post("https://discord.com/api/v10/oauth2/token", data={
                "client_id": client_id, "client_secret": _dash_env("DASHBOARD_CLIENT_SECRET"),
                "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
            }) as resp:
                token = await resp.json()
            access = token.get("access_token")
            if not access:
                raise _web.HTTPFound("/?error=token")
            headers = {"Authorization": f"Bearer {access}"}
            async with http.get("https://discord.com/api/v10/users/@me", headers=headers) as resp:
                user = await resp.json()
            async with http.get("https://discord.com/api/v10/users/@me/guilds", headers=headers) as resp:
                guilds = await resp.json()
    except (_aiohttp.ClientError, ValueError, asyncio.TimeoutError):
        raise _web.HTTPFound("/?error=network")
    if not isinstance(user, dict) or "id" not in user or not isinstance(guilds, list):
        raise _web.HTTPFound("/?error=token")
    if not dash_user_allowed(str(user["id"]), guilds):
        raise _web.HTTPFound("/?error=denied")
    response = _web.HTTPFound("/")
    _dash_start_session(response, request, str(user["id"]), user.get("global_name") or user.get("username") or "admin")
    response.del_cookie("dash_state", path="/")
    raise response


async def h_password_login(request):
    if not _dash_password_ready():
        return _json_error("El login con contraseña no está activado.", 400)
    if request.headers.get("X-Requested-With") != "dashboard":
        return _json_error("Petición no válida.", 403)
    ip = request.headers.get("X-Forwarded-For", request.remote or "?").split(",")[0].strip()
    count, start = _login_attempts.get(ip, (0, _time.time()))
    if _time.time() - start > 600:
        count, start = 0, _time.time()
    if count >= 5:
        return _json_error("Demasiados intentos. Espera unos minutos.", 429)
    try:
        body = await request.json()
    except ValueError:
        return _json_error("JSON inválido.", 400)
    password = str(body.get("password", "")) if isinstance(body, dict) else ""
    if not _hmac.compare_digest(password.encode(), _dash_env("DASHBOARD_PASSWORD").encode()):
        _login_attempts[ip] = (count + 1, start)
        return _json_error("Contraseña incorrecta.", 401)
    _login_attempts.pop(ip, None)
    response = _web.json_response({"ok": True})
    _dash_start_session(response, request, "password", "Administrador")
    return response


async def h_logout(request):
    if request.headers.get("X-Requested-With") != "dashboard":
        return _json_error("Petición no válida.", 403)
    response = _web.json_response({"ok": True})
    response.del_cookie("dash_session", path="/")
    return response


async def h_config_get(request):
    _, error = await _dash_guard(request)
    if error:
        return error
    return _web.json_response({"ok": True, "groups": config_snapshot()})


async def h_config_post(request):
    session, error = await _dash_guard(request, write=True)
    if error:
        return error
    try:
        body = await request.json()
    except ValueError:
        return _json_error("JSON inválido.", 400)
    values = body.get("values") if isinstance(body, dict) else None
    if not isinstance(values, dict) or not values:
        return _json_error("No hay cambios que guardar.", 400)
    clean, errors = await config_save(values, session["uid"], session["name"])
    if errors:
        return _web.json_response({"ok": False, "error": "Revisa los valores.", "errors": errors}, status=400)
    return _web.json_response({"ok": True, "saved": len(clean), "groups": config_snapshot()})


async def h_config_reset(request):
    session, error = await _dash_guard(request, write=True)
    if error:
        return error
    try:
        body = await request.json()
    except ValueError:
        return _json_error("JSON inválido.", 400)
    group_id = body.get("group") if isinstance(body, dict) else None
    groups = {g["id"]: g for g in config_groups()}
    if group_id not in groups:
        return _json_error("Grupo desconocido.", 400)
    defaults = {f["key"]: config_default(f["key"]) for f in groups[group_id]["fields"]}
    clean, errors = await config_save(defaults, session["uid"], session["name"])
    if errors:
        return _web.json_response({"ok": False, "error": "No se pudo restablecer.", "errors": errors}, status=400)
    return _web.json_response({"ok": True, "groups": config_snapshot()})


async def h_stats(request):
    _, error = await _dash_guard(request)
    if error:
        return error
    return _web.json_response({"ok": True, "stats": await dashboard_stats(), "audit": await dashboard_audit()})


async def h_event(request):
    session, error = await _dash_guard(request, write=True)
    if error:
        return error
    try:
        body = await request.json()
        hours = int(body.get("hours", 0))
        multiplier = int(body.get("multiplier") or 2)
    except (ValueError, TypeError, AttributeError):
        return _json_error("Horas o multiplicador inválidos.", 400)
    if not 0 <= hours <= 168:
        return _json_error("Las horas deben estar entre 0 y 168.", 400)
    if hours > 0 and not 2 <= multiplier <= MANUAL_EVENT_MAX_MULTIPLIER:
        return _json_error(f"El multiplicador debe estar entre 2 y {MANUAL_EVENT_MAX_MULTIPLIER}.", 400)
    return _web.json_response({"ok": True, "message": await dashboard_set_event(hours, multiplier)})


def build_dashboard_app():
    app = _web.Application()
    app.add_routes([
        _web.get("/", h_index),
        _web.get("/healthz", h_health),
        _web.get("/login", h_login),
        _web.get("/callback", h_callback),
        _web.post("/login/password", h_password_login),
        _web.post("/logout", h_logout),
        _web.get("/api/me", h_me),
        _web.get("/api/config", h_config_get),
        _web.post("/api/config", h_config_post),
        _web.post("/api/config/reset", h_config_reset),
        _web.get("/api/stats", h_stats),
        _web.post("/api/event", h_event),
    ])
    return app


_dashboard_runner = None


async def dashboard_start():
    """Arranca el panel web (una sola vez). Sin metodo de login configurado, no se abre."""
    global _dashboard_runner
    if _dashboard_runner is not None:
        return
    if not (_dash_oauth_ready() or _dash_password_ready()):
        print("Panel web desactivado: define DASHBOARD_CLIENT_SECRET (login con Discord) "
              "o DASHBOARD_PASSWORD (login con contraseña) para activarlo.")
        return
    port = int(os.environ.get("PORT", "8080"))
    runner = _web.AppRunner(build_dashboard_app())
    await runner.setup()
    await _web.TCPSite(runner, "0.0.0.0", port).start()
    _dashboard_runner = runner
    print(f"Panel web activo en el puerto {port}")


DASHBOARD_HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Casino Bot · Panel</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 100 100%27><text y=%27.9em%27 font-size=%2790%27>🎰</text></svg>">
<style>
:root{--bg:#0e1015;--panel:#161922;--panel2:#1c2030;--line:#272c3b;--text:#e8eaf0;--muted:#8b93a8;--accent:#5865f2;--accent2:#7983f5;--ok:#2ecc71;--warn:#f1c40f;--bad:#ed4245}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
button{font:inherit;cursor:pointer}
a{color:var(--accent2)}
.muted{color:var(--muted)}
.top{display:flex;align-items:center;justify-content:space-between;padding:12px 18px;background:var(--panel);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
.brand{font-weight:700;font-size:17px}.brand span{margin-left:8px;font-size:11px;background:var(--accent);padding:2px 7px;border-radius:99px;vertical-align:middle}
.user{display:flex;align-items:center;gap:10px;color:var(--muted)}
.layout{display:flex;min-height:calc(100vh - 54px)}
nav{width:230px;flex:none;background:var(--panel);border-right:1px solid var(--line);padding:12px 8px;overflow-y:auto;position:sticky;top:54px;height:calc(100vh - 54px)}
nav button{display:flex;gap:10px;align-items:center;width:100%;text-align:left;background:none;border:0;color:var(--muted);padding:9px 12px;border-radius:8px;margin-bottom:2px}
nav button:hover{background:var(--panel2);color:var(--text)}
nav button.active{background:var(--accent);color:#fff}
main{flex:1;min-width:0;padding:22px 24px 110px;max-width:900px}
h1{margin:0 0 4px;font-size:24px}h3{margin:0 0 6px;font-size:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:6px 16px;margin:14px 0}
.card h3{padding-top:12px}
.row{display:grid;grid-template-columns:1fr auto;gap:4px 14px;align-items:center;padding:12px 0;border-top:1px solid var(--line)}
.card h3+.row,.card>.row:first-child{border-top:0}
.lab b{font-weight:600}.lab small{display:block;color:var(--muted);font-size:12.5px}
.ctl{display:flex;align-items:center;gap:8px}
.ctl input[type=number]{width:170px;background:var(--bg);border:1px solid var(--line);color:var(--text);padding:8px 10px;border-radius:8px;font:inherit;text-align:right}
.ctl input[type=number]:focus{outline:2px solid var(--accent);border-color:transparent}
.unit{color:var(--muted);font-size:12.5px;min-width:28px}
.hint{grid-column:1/-1;font-size:12px;color:var(--muted);text-align:right;min-height:0}
.row.dirty .ctl input{border-color:var(--warn)}
.row.bad .ctl input{border-color:var(--bad)}
.row.dirty .hint{color:var(--warn)}
.reset{background:none;border:1px solid var(--line);color:var(--muted);border-radius:8px;padding:6px 9px}
.reset:hover{color:var(--text);border-color:var(--muted)}
.reset[hidden]{display:none}
.switch{appearance:none;width:44px;height:24px;border-radius:99px;background:#3a3f52;position:relative;cursor:pointer;transition:.15s;border:0}
.switch::after{content:"";position:absolute;top:3px;left:3px;width:18px;height:18px;border-radius:50%;background:#fff;transition:.15s}
.switch:checked{background:var(--ok)}.switch:checked::after{left:23px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px;margin:14px 0}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.stat small{color:var(--muted)}.stat b{display:block;font-size:22px;margin-top:2px}
.btn{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:9px 16px;font-weight:600}
.btn:hover{background:var(--accent2)}.btn.ok{background:var(--ok);color:#06210f}
.ghost{background:none;border:1px solid var(--line);color:var(--text);border-radius:8px;padding:8px 14px}
.ghost:hover{border-color:var(--muted)}.ghost.danger{color:var(--bad);margin-top:6px}
.savebar{position:fixed;left:50%;transform:translateX(-50%);bottom:16px;background:var(--panel2);border:1px solid var(--warn);border-radius:12px;padding:10px 14px;display:flex;gap:12px;align-items:center;z-index:9;box-shadow:0 8px 30px #0008;max-width:calc(100vw - 24px)}
.hidden{display:none!important}
#toast{position:fixed;top:64px;right:14px;max-width:min(420px,calc(100vw - 28px));z-index:20;display:flex;flex-direction:column;gap:8px}
.toast{background:var(--panel2);border:1px solid var(--line);border-left:4px solid var(--ok);padding:10px 14px;border-radius:8px;white-space:pre-line}
.toast.err{border-left-color:var(--bad)}
.login{max-width:420px;margin:12vh auto;padding:0 16px}
.login .card{padding:22px}.login h1{text-align:center}
.login input{width:100%;background:var(--bg);border:1px solid var(--line);color:var(--text);padding:10px;border-radius:8px;font:inherit;margin:8px 0}
.login .btn{width:100%;display:block;text-align:center;text-decoration:none;margin-top:8px}
.err{color:var(--bad)}
table{width:100%;border-collapse:collapse;font-size:13.5px}th,td{text-align:left;padding:8px 6px;border-top:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-weight:500;border-top:0}
.inline{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:10px 0}
.inline input{width:90px;background:var(--bg);border:1px solid var(--line);color:var(--text);padding:8px;border-radius:8px;font:inherit}
@media(max-width:760px){
 .layout{flex-direction:column}
 nav{width:auto;height:auto;position:sticky;top:54px;z-index:4;display:flex;overflow-x:auto;padding:8px;border-right:0;border-bottom:1px solid var(--line)}
 nav button{white-space:nowrap;width:auto;margin:0 4px 0 0;padding:8px 12px}
 main{padding:16px 12px 120px}
 .row{grid-template-columns:1fr}.ctl{justify-content:space-between}.ctl input[type=number]{width:100%;flex:1}.hint{text-align:left}
}
</style>
</head>
<body>
<div id="app"></div>
<div id="toast"></div>
<script>
"use strict";
const root = document.getElementById('app');
const S = {me: null, groups: [], stats: null, audit: [], view: 'overview', edits: {}, invalid: new Set()};
const fmt = n => Number(n).toLocaleString('en-US');

function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, '');
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

async function api(path, method = 'GET', body) {
  const opts = {method, headers: {'X-Requested-With': 'dashboard'}, credentials: 'same-origin'};
  if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  let res;
  try { res = await fetch(path, opts); } catch (e) { return {status: 0, data: {ok: false, error: 'Sin conexión con el bot.'}}; }
  let data = {};
  try { data = await res.json(); } catch (e) {}
  return {status: res.status, data};
}

function toast(msg, isErr) {
  const t = h('div', {class: 'toast' + (isErr ? ' err' : '')}, msg);
  document.getElementById('toast').append(t);
  setTimeout(() => t.remove(), isErr ? 7000 : 3000);
}

/* ---------------------------------------------------------------- login */
function renderLogin(me) {
  const errors = {oauth: 'El login con Discord no está configurado.', state: 'La sesión de login expiró. Intenta de nuevo.',
    token: 'Discord rechazó el login. Intenta de nuevo.', network: 'No pude hablar con Discord. Intenta de nuevo.',
    denied: 'Tu cuenta no tiene permiso para usar este panel.'};
  const code = new URLSearchParams(location.search).get('error');
  const card = h('div', {class: 'card'}, h('h1', {}, '🎰 Casino Bot'), h('p', {class: 'muted', style: 'text-align:center'}, 'Panel de configuración'));
  if (code) card.append(h('p', {class: 'err'}, errors[code] || 'No se pudo iniciar sesión.'));
  if (me.discord) card.append(h('a', {class: 'btn', href: '/login'}, 'Iniciar sesión con Discord'));
  if (me.password) {
    const pw = h('input', {type: 'password', placeholder: 'Contraseña del panel', autocomplete: 'current-password'});
    const msg = h('p', {class: 'err'});
    const go = async () => {
      const {data} = await api('/login/password', 'POST', {password: pw.value});
      if (data.ok) boot(); else msg.textContent = data.error || 'Error.';
    };
    pw.addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
    card.append(h('div', {style: me.discord ? 'margin-top:16px' : ''}, pw, h('button', {class: 'btn', style: 'width:100%', onclick: go}, 'Entrar'), msg));
  }
  if (!me.discord && !me.password) card.append(h('p', {class: 'err'}, 'No hay ningún método de login configurado.'));
  root.replaceChildren(h('div', {class: 'login'}, card));
}

/* ---------------------------------------------------------------- app */
function nav() {
  const items = [{id: 'overview', icon: '📊', title: 'Resumen'}, ...S.groups];
  return h('nav', {}, items.map(g => {
    const dirty = g.fields && g.fields.some(f => f.key in S.edits);
    return h('button', {class: g.id === S.view ? 'active' : '', onclick: () => { S.view = g.id; location.hash = g.id; renderApp(); }},
      g.icon, ' ', g.title, dirty ? ' •' : '');
  }));
}

function renderApp() {
  S.invalid = new Set();
  root.replaceChildren(
    h('header', {class: 'top'},
      h('div', {class: 'brand'}, '🎰 Casino Bot', h('span', {}, 'Panel')),
      h('div', {class: 'user'}, S.me.user.name, h('button', {class: 'ghost', onclick: logout}, 'Salir'))),
    h('div', {class: 'layout'}, nav(), h('main', {id: 'main'}, view())),
    h('div', {id: 'savebar', class: 'savebar hidden'},
      h('span', {id: 'savecount'}), h('button', {class: 'ghost', onclick: discard}, 'Descartar'),
      h('button', {class: 'btn ok', onclick: save}, 'Guardar cambios')));
  updateSavebar();
}

function view() {
  if (S.view === 'overview') return overview();
  const g = S.groups.find(x => x.id === S.view);
  return g ? groupView(g) : overview();
}

function updateSavebar() {
  const n = Object.keys(S.edits).length + S.invalid.size;
  const bar = document.getElementById('savebar');
  if (!bar) return;
  bar.classList.toggle('hidden', n === 0);
  document.getElementById('savecount').textContent = n + (n === 1 ? ' cambio sin guardar' : ' cambios sin guardar');
}

function groupView(g) {
  const wrap = h('div', {}, h('h1', {}, g.icon + ' ' + g.title), h('p', {class: 'muted'}, g.desc));
  const blocks = new Map();
  for (const f of g.fields) { const k = f.sub || ''; if (!blocks.has(k)) blocks.set(k, []); blocks.get(k).push(f); }
  for (const [sub, fields] of blocks) {
    const card = h('section', {class: 'card'});
    if (sub) card.append(h('h3', {}, sub));
    fields.forEach(f => card.append(fieldRow(f)));
    wrap.append(card);
  }
  wrap.append(h('button', {class: 'ghost danger', onclick: () => resetGroup(g)}, 'Restablecer este grupo a los valores por defecto'));
  return wrap;
}

function fieldRow(f) {
  const cur = (f.key in S.edits) ? S.edits[f.key] : f.value;
  const isBool = f.type === 'bool';
  const input = isBool
    ? h('input', {type: 'checkbox', class: 'switch'})
    : h('input', {type: 'number', inputmode: f.type === 'int' ? 'numeric' : 'decimal', min: f.min, max: f.max, step: f.step || 1, value: cur});
  if (isBool) input.checked = !!cur;
  const hint = h('div', {class: 'hint'});
  const reset = h('button', {class: 'reset', title: 'Valor por defecto', hidden: true}, '↺');
  const row = h('div', {class: 'row'},
    h('div', {class: 'lab'}, h('b', {}, f.label), f.help ? h('small', {}, f.help) : null),
    h('div', {class: 'ctl'}, input, f.unit ? h('span', {class: 'unit'}, f.unit) : null, reset), hint);

  const refresh = () => {
    const val = isBool ? input.checked : Number(input.value);
    const valid = isBool || (input.value !== '' && Number.isFinite(val) && val >= f.min && val <= f.max && (f.type !== 'int' || Number.isInteger(val)));
    row.classList.toggle('bad', !valid);
    if (valid) { S.invalid.delete(f.key); if (val === f.value) delete S.edits[f.key]; else S.edits[f.key] = val; }
    else { S.invalid.add(f.key); delete S.edits[f.key]; }
    row.classList.toggle('dirty', valid && val !== f.value);
    reset.hidden = !(valid ? val !== f.default : true);
    const parts = [];
    if (!isBool && valid) parts.push(fmt(val));
    if (!valid) parts.push('Valor no válido (' + fmt(f.min) + ' a ' + fmt(f.max) + ')');
    else if (val !== f.default) parts.push('por defecto: ' + (isBool ? (f.default ? 'sí' : 'no') : fmt(f.default)));
    hint.textContent = parts.join(' · ');
    updateSavebar();
  };
  input.addEventListener('input', refresh);
  reset.addEventListener('click', () => { if (isBool) input.checked = !!f.default; else input.value = f.default; refresh(); });
  refresh();
  return row;
}

function discard() { S.edits = {}; renderApp(); }

async function save() {
  if (S.invalid.size) { toast('Corrige los valores en rojo antes de guardar.', true); return; }
  if (!Object.keys(S.edits).length) return;
  const {data} = await api('/api/config', 'POST', {values: S.edits});
  if (data.ok) { S.groups = data.groups; S.edits = {}; toast('Guardado ✅ (' + data.saved + ')'); renderApp(); }
  else toast((data.errors && data.errors.length ? data.errors : [data.error || 'Error']).join('\n'), true);
}

async function resetGroup(g) {
  if (!confirm('¿Restablecer "' + g.title + '" a los valores por defecto?')) return;
  const {data} = await api('/api/config/reset', 'POST', {group: g.id});
  if (data.ok) { g.fields.forEach(f => delete S.edits[f.key]); S.groups = data.groups; toast('Restablecido ✅'); renderApp(); }
  else toast((data.errors || [data.error || 'Error']).join('\n'), true);
}

/* ---------------------------------------------------------------- resumen */
function cleanEvent(text) {
  return String(text).replace(/<t:(\d+):[a-zA-Z]>/g, (_, s) => new Date(Number(s) * 1000).toLocaleString()).replace(/\*\*/g, '').replace(/`/g, '');
}

function overview() {
  const wrap = h('div', {}, h('h1', {}, '📊 Resumen'), h('p', {class: 'muted'}, 'Estado general del casino y accesos rápidos.'));
  const st = S.stats;
  if (!st) { wrap.append(h('p', {class: 'muted'}, 'Cargando…')); return wrap; }
  const stat = (label, val) => h('div', {class: 'stat'}, h('small', {}, label), h('b', {}, val));
  wrap.append(h('div', {class: 'grid'},
    stat('👥 Jugadores', fmt(st.users)), stat('👛 Dinero en carteras', fmt(st.money_wallet) + ' 🪙'),
    stat('🏦 Dinero en bancos', fmt(st.money_bank) + ' 🪙'), stat('🌐 Servidores', fmt(st.guilds)),
    stat('🛡️ Clanes', fmt(st.clans)), stat('💳 Préstamos activos', fmt(st.loans)),
    stat('🤝 Roles prestados', fmt(st.role_loans)), stat('🏪 Anuncios en el mercado', fmt(st.listings))));

  if (st.per_guild && st.per_guild.length) {
    const tb = h('table', {}, h('tr', {}, h('th', {}, 'Servidor'), h('th', {}, 'Jugadores'), h('th', {}, 'Dinero total'), h('th', {}, 'Collect')));
    st.per_guild.forEach(g => tb.append(h('tr', {}, h('td', {}, g.name), h('td', {}, fmt(g.users)), h('td', {}, fmt(g.money) + ' 🪙'), h('td', {}, 'x' + g.event_multiplier))));
    wrap.append(h('section', {class: 'card'}, h('h3', {}, '🌐 Economía por servidor'), h('div', {style: 'overflow-x:auto'}, tb)));
  }
  const mult = h('input', {type: 'number', min: 2, max: 50, value: 2});
  const hours = h('input', {type: 'number', min: 1, max: 168, value: 24});
  const evt = async (hrs) => {
    const {data} = await api('/api/event', 'POST', {hours: hrs, multiplier: Number(mult.value) || 2});
    toast(data.ok ? data.message : (data.error || 'Error'), !data.ok);
    await loadStats(); renderApp();
  };
  wrap.append(h('section', {class: 'card'}, h('h3', {}, '🎉 Evento de collect (todos los servidores)'),
    h('p', {class: 'muted', style: 'white-space:pre-line'}, cleanEvent(st.event_text)),
    h('div', {class: 'inline'}, h('span', {class: 'muted'}, 'Multiplicador ×'), mult, hours, h('span', {class: 'muted'}, 'horas'),
      h('button', {class: 'btn', onclick: () => evt(Number(hours.value) || 0)}, 'Activar ahora'),
      h('button', {class: 'ghost', onclick: () => evt(0)}, 'Terminar evento manual'))));

  const card = h('section', {class: 'card'}, h('h3', {}, '🕘 Últimos cambios'));
  if (!S.audit.length) card.append(h('p', {class: 'muted'}, 'Todavía no se ha cambiado nada desde el panel.'));
  else {
    const tb = h('table', {}, h('tr', {}, h('th', {}, 'Cuándo'), h('th', {}, 'Quién'), h('th', {}, 'Ajuste'), h('th', {}, 'Cambio')));
    S.audit.forEach(a => tb.append(h('tr', {},
      h('td', {}, new Date(a.ts + 'Z').toLocaleString()), h('td', {}, a.user), h('td', {}, a.label),
      h('td', {}, show(a.old) + ' → ' + show(a.new)))));
    card.append(h('div', {style: 'overflow-x:auto'}, tb));
  }
  wrap.append(card);
  return wrap;
}
function show(v) { try { const x = JSON.parse(v); return typeof x === 'number' ? fmt(x) : (x === true ? 'sí' : x === false ? 'no' : String(x)); } catch (e) { return String(v); } }

/* ---------------------------------------------------------------- arranque */
async function loadStats() {
  const {data} = await api('/api/stats');
  if (data.ok) { S.stats = data.stats; S.audit = data.audit; }
}
async function logout() { await api('/logout', 'POST', {}); S.edits = {}; boot(); }

async function boot() {
  const {data: me} = await api('/api/me');
  if (!me.authenticated) { renderLogin(me); return; }
  S.me = me;
  const cfg = await api('/api/config');
  if (!cfg.data.ok) { renderLogin(me); return; }
  S.groups = cfg.data.groups;
  const wanted = location.hash.slice(1);
  S.view = (wanted && S.groups.some(g => g.id === wanted)) ? wanted : 'overview';
  renderApp();
  await loadStats();
  if (S.view === 'overview') renderApp();
}

window.addEventListener('beforeunload', e => { if (Object.keys(S.edits).length) { e.preventDefault(); e.returnValue = ''; } });
boot();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: Falta la variable de entorno DISCORD_TOKEN")
        exit(1)
    client.run(TOKEN)
