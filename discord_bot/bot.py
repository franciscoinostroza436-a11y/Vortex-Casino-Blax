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
        "name": "🛡️ Escudo Anti-Robos",
        "price": 800_000,
        "description": "Actívalo con `/use` y te protege de robos durante **1h 30m**. ¡Consumible!",
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

ROLE_ITEMS = [k for k, v in SHOP_ITEMS.items() if v["category"] == "rol"]
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
        return 5_000
    day = min(streak, 30)
    return 50_000 + (day - 2) * 10_000

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
                ROLE_ITEMS,
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


async def collect_available_role_earnings(
    user_id: str,
    now: datetime | None = None,
) -> tuple[list[str], list[str], list[tuple[str, datetime]]]:
    """Collect only roles whose individual cooldown has expired."""
    role_placeholders = ",".join("?" for _ in ROLE_ITEMS)
    now = now or datetime.utcnow()
    owned_roles: list[str] = []
    ready_roles: list[str] = []
    waiting_roles: list[tuple[str, datetime]] = []

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute(
            f"SELECT item_id FROM inventory WHERE user_id=? AND quantity > 0 "
            f"AND item_id IN ({role_placeholders})",
            (user_id, *ROLE_ITEMS),
        ) as cursor:
            owned_roles = [row[0] for row in await cursor.fetchall()]

        if not owned_roles:
            await db.commit()
            return [], [], []

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
            total_bonus = sum(SHOP_ITEMS[role_id]["collect_bonus"] for role_id in ready_roles)
            for role_id in ready_roles:
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

    return owned_roles, ready_roles, waiting_roles


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


async def lottery_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        await asyncio.sleep(60)
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
            continue

        last_dt = datetime.fromisoformat(last_draw)
        if (now - last_dt) >= timedelta(days=7):
            await run_lottery_draw()


@client.event
async def on_ready():
    await init_db()
    await tree.sync()
    asyncio.create_task(lottery_loop())
    print(f"Bot conectado como {client.user}")


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
    owned_roles, ready_roles, waiting_roles = await collect_available_role_earnings(user_id)

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

    total_bonus = sum(SHOP_ITEMS[r]["collect_bonus"] for r in ready_roles)
    new_balance = await get_balance(user_id)
    embed = discord.Embed(title="💰 ¡Ganancias Recogidas!", color=0x00FF88)
    lines = "\n".join(
        f"{SHOP_ITEMS[r]['name']} → +**{SHOP_ITEMS[r]['collect_bonus']:,}** 🪙"
        for r in ready_roles
    )
    embed.description = (
        f"{lines}\n\n"
        f"**Total:** +**{total_bonus:,}** 🪙\n"
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
        if diff < timedelta(hours=1):
            remaining = timedelta(hours=1) - diff
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
        "rol": "👑 Roles con /collect",
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


async def complete_shop_purchase(user: discord.User | discord.Member, item_id: str) -> discord.Embed:
    item_data = SHOP_ITEMS[item_id]
    user_id = str(user.id)
    await get_or_create_user(user_id, user.name)
    balance = await get_balance(user_id)

    if balance < item_data["price"]:
        embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
        embed.description = (
            f"Necesitas **{item_data['price']:,}** 🪙 y tienes **{balance:,}** 🪙."
        )
        return embed

    await update_balance(user_id, -item_data["price"])
    await add_to_inventory(user_id, item_id)
    new_balance = await get_balance(user_id)

    embed = discord.Embed(title="🛍️ ¡Compra Exitosa!", color=0x00FF88)
    description = (
        f"Compraste **{item_data['name']}**.\n"
        f"{item_data['description']}\n\n"
        f"Gastaste: **{item_data['price']:,}** 🪙\n"
        f"Saldo restante: **{new_balance:,}** 🪙"
    )
    if item_data["category"] == "rol":
        description += "\n\n💡 Usa `/collect` para reclamar las ganancias disponibles."
    if item_data["category"] == "proteccion":
        description += "\n\n💡 Se activa automáticamente si alguien intenta robarte."
    embed.description = description
    return embed


class ShopBuySelect(discord.ui.Select):
    def __init__(self, owner_id: str):
        self.owner_id = owner_id
        options = []
        for item_id, item in SHOP_ITEMS.items():
            category = "Rol" if item["category"] == "rol" else item["category"].title()
            detail = f"{item['price']:,} monedas · {category}"
            if item["category"] == "rol":
                detail += f" · +{item['collect_bonus']:,} cada {item['collect_hours']}h"
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
        view = self.view
        if view is None or view.purchase_completed:
            await interaction.response.send_message(
                "Este panel de compra ya fue utilizado. Ejecuta `/buy` para abrir otro.",
                ephemeral=True,
            )
            return
        view.purchase_completed = True
        result = await complete_shop_purchase(interaction.user, self.values[0])
        await interaction.response.edit_message(embed=result, view=None)


class ShopBuyView(discord.ui.View):
    def __init__(self, owner_id: str):
        super().__init__(timeout=180)
        self.purchase_completed = False
        self.add_item(ShopBuySelect(owner_id))


@tree.command(name="shop", description="Muestra los objetos disponibles en la tienda")
async def shop(interaction: discord.Interaction):
    await interaction.response.send_message(embed=build_shop_embed())


@tree.command(name="buy", description="Abre el panel de compra o compra un objeto por ID")
@app_commands.describe(item="ID del objeto; déjalo vacío para abrir el panel")
async def buy(interaction: discord.Interaction, item: str | None = None):
    if item is None:
        await get_or_create_user(str(interaction.user.id), interaction.user.name)
        await interaction.response.send_message(
            embed=build_shop_embed(panel=True),
            view=ShopBuyView(str(interaction.user.id)),
            ephemeral=True,
        )
        return

    item = normalize_shop_item_id(item)
    if item not in SHOP_ITEMS:
        ids = ", ".join(f"`{item_id}`" for item_id in SHOP_ITEMS)
        await interaction.response.send_message(
            f"❌ Objeto no encontrado. IDs válidos: {ids}", ephemeral=True
        )
        return

    embed = await complete_shop_purchase(interaction.user, item)
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
                "• Usa `/collect` para reclamar tus ganancias\n"
                "• Cada rol tiene su propio cooldown\n"
                "• `/collect` paga solo los roles que ya están listos"
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
    item = normalize_shop_item_id(item)
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
        now_dt = datetime.utcnow()
        shield_exp = now_dt + timedelta(minutes=90)
        await remove_from_inventory(user_id, "anti_rob")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET shield_until = ? WHERE user_id = ?", (shield_exp.isoformat(), user_id))
            await db.commit()
        embed = discord.Embed(title="🛡️ ¡Escudo Anti-Robos Activado!", color=0x3498DB)
        embed.description = (
            f"🔒 Estás protegido de robos durante **1 hora y 30 minutos**.\n\n"
            f"⏰ Expira a las **{shield_exp.strftime('%H:%M UTC')}**\n"
            f"📦 Escudos restantes: **{qty - 1}**"
        )
        await interaction.response.send_message(embed=embed)

    elif item_data["category"] == "rol":
        last_collect = await get_role_last_collect(user_id, item)
        now = datetime.utcnow()
        cooldown_hours = item_data["collect_hours"]
        if last_collect:
            last_dt = datetime.fromisoformat(last_collect)
            next_collect_at = last_dt + timedelta(hours=cooldown_hours)
            if now < next_collect_at:
                next_collect = f"en **{format_collect_wait(next_collect_at, now)}**"
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


class BetView(discord.ui.View):
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


class TournamentView(discord.ui.View):
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
            "`/use item` — Usar un objeto\n"
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

    embed.set_footer(text="🏦 El banco es seguro contra robos  •  Casino Bot")
    await interaction.response.send_message(embed=embed)


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


@tree.command(name="fighters", description="Muestra todos los luchadores disponibles para comprar")
async def fighters_slash(interaction: discord.Interaction):
    embed = discord.Embed(title="🥊 Luchadores del Casino", color=0xFF6B00)
    embed.description = "Compra un luchador con `/buyfighter <id>` y reta a otros con `/fight @usuario`.\n\u200b"
    for fid, f in FIGHTERS.items():
        embed.add_field(
            name=f"{f['name']} — `{fid}`",
            value=f"💰 {f['price']:,} 🪙\n❤️ HP: {f['hp']} | ⚔️ ATK: {f['attack']} | 🛡️ DEF: {f['defense']}\n_{f['description']}_",
            inline=False
        )
    await interaction.response.send_message(embed=embed)


@tree.command(name="buyfighter", description="Compra un luchador para pelear")
@app_commands.describe(luchador="ID del luchador (usa /fighters para ver la lista)")
async def buyfighter_slash(interaction: discord.Interaction, luchador: str):
    user_id = str(interaction.user.id)
    fid = luchador.lower().strip()
    if fid not in FIGHTERS:
        ids = ", ".join(f"`{k}`" for k in FIGHTERS)
        await interaction.response.send_message(f"❌ Luchador no encontrado. IDs válidos: {ids}", ephemeral=True)
        return
    await interaction.response.defer()
    await get_or_create_user(user_id, interaction.user.name)
    f = FIGHTERS[fid]
    bal = await get_balance(user_id)
    if bal < f["price"]:
        await interaction.followup.send(
            f"❌ Te faltan **{f['price'] - bal:,}** 🪙 para comprar **{f['name']}**.", ephemeral=True)
        return
    await update_balance(user_id, -f["price"])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO fighters (user_id, fighter_id) VALUES (?, ?)", (user_id, fid))
        await db.commit()
    embed = discord.Embed(title=f"🥊 ¡Luchador Comprado!", color=0x00FF88)
    embed.description = (
        f"Ahora tienes a **{f['name']}** en tu equipo.\n\n"
        f"❤️ HP: {f['hp']} | ⚔️ ATK: {f['attack']} | 🛡️ DEF: {f['defense']}\n\n"
        f"_Reta a alguien con `/fight @usuario`_"
    )
    await interaction.followup.send(embed=embed)


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

class FighterTournamentView(discord.ui.View):
    MAX_PLAYERS = 8

    def __init__(self, host_id: str, host_name: str):
        super().__init__(timeout=90)
        self.host_id = host_id
        self.host_name = host_name
        self.players: list[tuple[str, str, str]] = []  # (user_id, display_name, fighter_id)
        self.message: discord.Message | None = None
        self.started = False

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
            f"🏆 El campeón gana **{FIGHTER_TOURNAMENT_PRIZE:,}** 🪙\n"
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
            await channel.send(embed=embed)
            return

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
        await update_balance(champion[0], FIGHTER_TOURNAMENT_PRIZE)
        champ_bal = await get_balance(champion[0])

        embed = discord.Embed(title="🏆 ¡CAMPEÓN DEL TORNEO!", color=0xFFD700)
        embed.description = (
            f"👑 **<@{champion[0]}> es el campeón!**\n"
            f"Luchador: **{FIGHTERS[champion[2]]['name']}**\n\n"
            f"💰 Premio: **{FIGHTER_TOURNAMENT_PRIZE:,}** 🪙\n"
            f"💼 Saldo nuevo: **{champ_bal:,}** 🪙"
        )
        await channel.send(embed=embed)


@tree.command(name="addpuntos", description="Agrega puntos a los stats de tu luchador")
@app_commands.describe(stat="Stat a mejorar: ataque, defensa, salud", cantidad="Cuántos puntos invertir")
async def addpuntos_slash(interaction: discord.Interaction, stat: str, cantidad: int):
    user_id = str(interaction.user.id)
    stat = stat.lower().strip()
    if stat not in ("ataque", "defensa", "salud"):
        await interaction.response.send_message("❌ Stat inválido. Usa: `ataque`, `defensa` o `salud`.", ephemeral=True)
        return
    if cantidad <= 0:
        await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
        return
    await interaction.response.defer()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT fighter_id FROM fighters WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
    if not row:
        await interaction.followup.send("❌ No tienes luchador. Compra uno con `/buyfighter`.", ephemeral=True)
        return
    fid = row[0]
    s = await get_fighter_stats(user_id, fid)
    if s["points"] < cantidad:
        await interaction.followup.send(f"❌ Solo tienes **{s['points']}** puntos disponibles.", ephemeral=True)
        return
    col_map = {"ataque": "bonus_attack", "defensa": "bonus_defense", "salud": "bonus_hp"}
    val_map  = {"ataque": cantidad * 2, "defensa": cantidad * 2, "salud": cantidad * 5}
    col = col_map[stat]; bonus_gain = val_map[stat]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"INSERT INTO fighter_levels (user_id, fighter_id, points, {col}) VALUES (?,?,?,?) "
            f"ON CONFLICT(user_id, fighter_id) DO UPDATE SET points=points-?, {col}={col}+?",
            (user_id, fid, -cantidad, bonus_gain, cantidad, bonus_gain)
        )
        await db.commit()
    s2 = await get_fighter_stats(user_id, fid)
    stat_emoji = {"ataque": "⚔️", "defensa": "🛡️", "salud": "❤️"}[stat]
    embed = discord.Embed(title="📈 ¡Stat Mejorado!", color=0x00FF88)
    embed.description = (
        f"{stat_emoji} **{stat.capitalize()}** +{bonus_gain} puntos de stat\n"
        f"🎯 Puntos restantes: **{s2['points']}**\n\n"
        f"**Stats actuales de {s2['name']}:**\n"
        f"❤️ HP: **{s2['hp']}** | ⚔️ ATK: **{s2['attack']}** | 🛡️ DEF: **{s2['defense']}**"
    )
    await interaction.followup.send(embed=embed)


@tree.command(name="ftorneo", description="Crea un torneo de luchadores. El campeón gana 60 millones.")
async def ftorneo_slash(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    await interaction.response.defer()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT fighter_id FROM fighters WHERE user_id = ?", (uid,)) as cur:
            row = await cur.fetchone()
    if not row:
        await interaction.followup.send("❌ Necesitas un luchador para organizar un torneo. Compra uno con `/buyfighter`.", ephemeral=True)
        return
    view = FighterTournamentView(host_id=uid, host_name=interaction.user.display_name)
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


class LiveBetModal(discord.ui.Modal, title="🎰 Tus Apuestas"):
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


class LiveRouletteView(discord.ui.View):
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


async def _open_card_pack(interaction: discord.Interaction, tipo: str):
    pack_key = _PACK_ALIASES.get(tipo.lower().strip())
    if not pack_key:
        lines = "\n".join(
            f"{pt['emoji']} `{k}` — {pt['label']} · **{pt['price']:,}** 🪙"
            for k, pt in PACK_TYPES.items()
        )
        embed = discord.Embed(title="❌ Tipo de sobre inválido", color=0xFF4444,
                               description=f"Tipos disponibles:\n{lines}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    pt = PACK_TYPES[pack_key]
    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)
    bal = await get_balance(user_id)
    if bal < pt["price"]:
        embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
        embed.description = f"{pt['emoji']} **{pt['label']}** cuesta **{pt['price']:,}** 🪙. Tienes **{bal:,}** 🪙."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    await interaction.response.defer()
    await update_balance(user_id, -pt["price"])
    drawn = _draw_pack_cards(pack_key)
    for cid in drawn:
        await _add_card(user_id, cid)
    best_rarity = min((FOOTBALL_CARDS[cid]["rarity"] for cid in drawn),
                      key=lambda r: RARITY_CONFIG[r]["weight"])
    color = RARITY_CONFIG[best_rarity]["color"]
    rc = RARITY_CONFIG[best_rarity]
    title = f"{rc['emoji']} {pt['label']} — ¡{rc['label']}!" if rc["weight"] <= 4 else f"{pt['emoji']} {pt['label']} abierto"
    embed = discord.Embed(title=title, color=color)
    embed.description = f"**{interaction.user.display_name}** abrió un **{pt['label']}** y obtuvo:\n\n"
    embed.description += "\n".join(f"➤ {_card_line(cid)}" for cid in drawn)
    new_bal = await get_balance(user_id)
    embed.set_footer(text=f"💰 Saldo restante: {new_bal:,} 🪙")
    await interaction.followup.send(embed=embed)


@tree.command(name="abrirpaquete", description="Compra y abre un sobre de tarjetas de fútbol")
@app_commands.describe(tipo="Tipo de sobre: comun / poco_comun / raro / epico / legendario")
async def abrirpaquete_slash(interaction: discord.Interaction, tipo: str = "comun"):
    await _open_card_pack(interaction, tipo)


@tree.command(name="comprarsobre", description="Compra y abre un sobre de tarjetas de fútbol")
@app_commands.choices(tipo=[
    app_commands.Choice(name="Común — 1.000 monedas", value="comun"),
    app_commands.Choice(name="Poco común — 10.000 monedas", value="poco_comun"),
    app_commands.Choice(name="Raro — 50.000 monedas", value="raro"),
    app_commands.Choice(name="Épico — 150.000 monedas", value="epico"),
    app_commands.Choice(name="Legendario — 500.000 monedas", value="legendario"),
])
async def comprarsobre_slash(
    interaction: discord.Interaction,
    tipo: app_commands.Choice[str],
):
    await _open_card_pack(interaction, tipo.value)


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
    embed.set_footer(text="Usa /comprarsobre <tipo>  •  Ej: /comprarsobre raro")
    await interaction.response.send_message(embed=embed)


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
    title = "🏪 Mercado de Cartas"
    if rarity_key:
        rc = RARITY_CONFIG[rarity_key]
        title += f" — {rc['emoji']} {rc['label']}"
    embed = _market_embed(listings, title,
                          footer="Comprar: /comprar <#id>  •  Vender: /vender <carta> <precio>")
    embed.set_footer(text=f"{'Mostrando hasta 20 resultados' if listings else ''} · "
                         f"/comprar <id> para comprar · /vender <carta> <precio> para vender")
    await interaction.response.send_message(embed=embed)


@tree.command(name="comprar", description="Compra una carta del mercado")
@app_commands.describe(id="Número de la publicación (el #id que aparece en /mercado)")
async def comprar_slash(interaction: discord.Interaction, id: int):
    user_id = str(interaction.user.id)
    await get_or_create_user(user_id, interaction.user.name)
    listing = await _market_get_listing(id)
    if not listing:
        await interaction.response.send_message(f"❌ La publicación **#{id}** no existe o ya fue vendida.",
                                                  ephemeral=True)
        return
    lid, seller_id, card_id, price, ts = listing
    if seller_id == user_id:
        await interaction.response.send_message("❌ No puedes comprar tu propia carta.", ephemeral=True)
        return
    bal = await get_balance(user_id)
    if bal < price:
        await interaction.response.send_message(
            f"❌ Necesitas **{price:,}** 🪙 pero tienes **{bal:,}** 🪙.", ephemeral=True)
        return
    # Execute purchase
    await _market_delete_listing(lid)
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
    await interaction.response.send_message(embed=embed)
    # Notify seller in DMs if possible
    try:
        seller = await client.fetch_user(int(seller_id))
        dm_embed = discord.Embed(title="💰 ¡Vendiste una carta!", color=0x2ECC71)
        dm_embed.description = (
            f"**{interaction.user.display_name}** compró tu:\n"
            f"➤ {_card_line(card_id)}\n\n"
            f"Recibiste **{price:,}** 🪙 en tu balance."
        )
        await seller.send(embed=dm_embed)
    except Exception:
        pass


@tree.command(name="cancelarventa", description="Retira tu carta del mercado y devuélvela a tu colección")
@app_commands.describe(id="Número de la publicación a cancelar")
async def cancelarventa_slash(interaction: discord.Interaction, id: int):
    user_id = str(interaction.user.id)
    listing = await _market_get_listing(id)
    if not listing:
        await interaction.response.send_message(f"❌ La publicación **#{id}** no existe.", ephemeral=True)
        return
    lid, seller_id, card_id, price, ts = listing
    if seller_id != user_id:
        await interaction.response.send_message("❌ Esa publicación no es tuya.", ephemeral=True)
        return
    await _market_delete_listing(lid)
    await _add_card(user_id, card_id)
    c = FOOTBALL_CARDS[card_id]
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

class TradeView(discord.ui.View):
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

    # ,bal
    if cmd == "bal":
        await get_or_create_user(user_id, message.author.name)
        bal = await get_balance(user_id)
        bank_bal = await get_bank(user_id)
        total = bal + bank_bal
        embed = discord.Embed(title="💰 Tu Saldo", color=0xFFD700)
        embed.add_field(name="👛 Cartera", value=f"**{bal:,}** 🪙", inline=True)
        embed.add_field(name="🏦 Banco", value=f"**{bank_bal:,}** 🪙", inline=True)
        embed.add_field(name="📊 Total", value=f"**{total:,}** 🪙", inline=True)
        embed.set_footer(text=f"Casino Bot • {message.author.name} • El banco es seguro contra robos")
        await message.channel.send(embed=embed)

    # ,shop
    elif cmd == "shop":
        embed = discord.Embed(title="🏪 Tienda del Casino", color=0x9B59B6)
        embed.description = (
            "Usa `/buy` para abrir el panel de compra, `/buy <id_item>` o "
            "`,buy <id_item>` para comprar por ID. Los roles se cobran con `,collect`.\n"
        )
        categorias = {
            "proteccion": "🛡️ Protección",
            "rol": "👑 Roles con /collect",
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
        await message.channel.send(embed=embed)

    # ,collect
    elif cmd == "collect":
        await get_or_create_user(user_id, message.author.name)
        owned_roles, ready_roles, waiting_roles = await collect_available_role_earnings(user_id)

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

        total_bonus = sum(SHOP_ITEMS[r]["collect_bonus"] for r in ready_roles)
        new_balance = await get_balance(user_id)
        embed = discord.Embed(title="💰 ¡Ganancias Recogidas!", color=0x00FF88)
        lines = "\n".join(
            f"{SHOP_ITEMS[r]['name']} → +**{SHOP_ITEMS[r]['collect_bonus']:,}** 🪙"
            for r in ready_roles
        )
        embed.description = (
            f"{lines}\n\n"
            f"**Total:** +**{total_bonus:,}** 🪙\n"
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

    # ,work — gana monedas trabajando (cooldown 1h)
    elif cmd == "work":
        await get_or_create_user(user_id, message.author.name)
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT last_work FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                last_work = row[0] if row else None

        now = datetime.utcnow()
        if last_work:
            diff = now - datetime.fromisoformat(last_work)
            if diff < timedelta(seconds=30):
                remaining = timedelta(seconds=30) - diff
                secs = int(remaining.total_seconds())
                embed = discord.Embed(title="⏰ Aún estás trabajando", color=0xFF4444)
                embed.description = f"Descansa **{secs}s** antes de volver a trabajar."
                await message.channel.send(embed=embed)
                return

        earned = random.randint(1000, 100000)
        trabajos = [
            ("👨‍🍳 Cocinero", f"Preparaste platos toda la noche y ganaste **{earned:,}** 🪙."),
            ("🚗 Taxista", f"Llevaste pasajeros por toda la ciudad y ganaste **{earned:,}** 🪙."),
            ("💻 Programador", f"Terminaste un proyecto freelance y ganaste **{earned:,}** 🪙."),
            ("🎸 Músico", f"Tocaste en una plaza y la gente aplaudió. Ganaste **{earned:,}** 🪙."),
            ("📦 Repartidor", f"Repartiste 30 pedidos y ganaste **{earned:,}** 🪙."),
            ("🧹 Limpiador", f"Limpiaste el casino de arriba a abajo. Ganaste **{earned:,}** 🪙."),
        ]
        titulo, desc = random.choice(trabajos)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET balance = balance + ?, last_work = ? WHERE user_id = ?",
                             (earned, now.isoformat(), user_id))
            await db.commit()

        new_bal = await get_balance(user_id)
        embed = discord.Embed(title=f"💼 {titulo}", color=0x00FF88)
        embed.description = f"{desc}\n\n👛 Saldo actual: **{new_bal:,}** 🪙"
        await message.channel.send(embed=embed)

    # ,slut — 60% ganar / 40% perder (cooldown 30min)
    elif cmd == "slut":
        await get_or_create_user(user_id, message.author.name)
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT last_slut FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                last_slut = row[0] if row else None

        now = datetime.utcnow()
        if last_slut:
            diff = now - datetime.fromisoformat(last_slut)
            if diff < timedelta(seconds=30):
                remaining = timedelta(seconds=30) - diff
                secs = int(remaining.total_seconds())
                embed = discord.Embed(title="⏰ Cooldown Activo", color=0xFF4444)
                embed.description = f"Espera **{secs}s** para volver a intentarlo."
                await message.channel.send(embed=embed)
                return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET last_slut = ? WHERE user_id = ?", (now.isoformat(), user_id))
            await db.commit()

        success = random.random() < 0.60
        if success:
            earned = random.randint(1000, 100000)
            escenas = [
                f"💋 Una noche rentable. Ganaste **{earned:,}** 🪙.",
                f"💄 El cliente quedó satisfecho. Ganaste **{earned:,}** 🪙.",
                f"🌹 Noche de buenas propinas. Ganaste **{earned:,}** 🪙.",
            ]
            await update_balance(user_id, earned)
            new_bal = await get_balance(user_id)
            embed = discord.Embed(title="💋 ¡Éxito!", color=0xFF69B4)
            embed.description = f"{random.choice(escenas)}\n\n👛 Saldo: **{new_bal:,}** 🪙"
        else:
            lost = random.randint(1000, 100000)
            bal = await get_balance(user_id)
            lost = min(lost, bal)
            await update_balance(user_id, -lost)
            new_bal = await get_balance(user_id)
            embed = discord.Embed(title="🚔 ¡Te Pillaron!", color=0xFF4444)
            embed.description = (
                f"La policía te arrestó. Multa: **{lost:,}** 🪙.\n\n"
                f"👛 Saldo: **{new_bal:,}** 🪙"
            )
        await message.channel.send(embed=embed)

    # ,crime — 60% ganar / 40% perder (cooldown 1h)
    elif cmd == "crime":
        await get_or_create_user(user_id, message.author.name)
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT last_crime FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                last_crime = row[0] if row else None

        now = datetime.utcnow()
        if last_crime:
            diff = now - datetime.fromisoformat(last_crime)
            if diff < timedelta(seconds=30):
                remaining = timedelta(seconds=30) - diff
                secs = int(remaining.total_seconds())
                embed = discord.Embed(title="⏰ Cooldown Activo", color=0xFF4444)
                embed.description = f"Espera **{secs}s** antes de cometer otro crimen."
                await message.channel.send(embed=embed)
                return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET last_crime = ? WHERE user_id = ?", (now.isoformat(), user_id))
            await db.commit()

        success = random.random() < 0.60
        if success:
            earned = random.randint(1000, 100000)
            crimenes = [
                f"🏦 Asaltaste un banco pequeño y escapaste con **{earned:,}** 🪙.",
                f"💎 Vendiste joyas robadas en el mercado negro. Ganaste **{earned:,}** 🪙.",
                f"🎰 Hackeaste una slot machine. Ganaste **{earned:,}** 🪙.",
                f"🚗 Robaste un auto de lujo y lo vendiste. Ganaste **{earned:,}** 🪙.",
                f"📱 Estafaste a un coleccionista con NFTs falsos. Ganaste **{earned:,}** 🪙.",
            ]
            await update_balance(user_id, earned)
            new_bal = await get_balance(user_id)
            embed = discord.Embed(title="🦹 ¡Crimen Exitoso!", color=0x9B59B6)
            embed.description = f"{random.choice(crimenes)}\n\n👛 Saldo: **{new_bal:,}** 🪙"
        else:
            lost = random.randint(1000, 100000)
            bal = await get_balance(user_id)
            lost = min(lost, bal)
            await update_balance(user_id, -lost)
            new_bal = await get_balance(user_id)
            fracasos = [
                f"🚔 La policía te atrapó en pleno acto. Multa: **{lost:,}** 🪙.",
                f"😬 Tu cómplice te traicionó. Perdiste **{lost:,}** 🪙 en sobornos.",
                f"🔒 Las cámaras te grabaron. Multa judicial: **{lost:,}** 🪙.",
            ]
            embed = discord.Embed(title="🚔 ¡Operación Fallida!", color=0xFF4444)
            embed.description = f"{random.choice(fracasos)}\n\n👛 Saldo: **{new_bal:,}** 🪙"
        await message.channel.send(embed=embed)

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
            if diff < timedelta(hours=1):
                remaining = timedelta(hours=1) - diff
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

        success = random.random() < 0.40
        if success:
            pct = random.uniform(0.10, 0.40)
            stolen = max(1, int(victim_balance * pct))
            stolen = min(stolen, victim_balance)
            await update_balance(victim_id, -stolen)
            await update_balance(user_id, stolen)
            robber_balance = await get_balance(user_id)
            embed = discord.Embed(title="🦹 ¡Robo Exitoso!", color=0x00FF88)
            embed.description = (
                f"¡Le robaste **{stolen:,}** 🪙 a **{target.mention}**!\n\n"
                f"Tu saldo: **{robber_balance:,}** 🪙"
            )
        else:
            fine = max(1, int(victim_balance * 0.10))
            robber_balance = await get_balance(user_id)
            fine = min(fine, robber_balance)
            await update_balance(user_id, -fine)
            embed = discord.Embed(title="🚔 ¡Te Atraparon!", color=0xFF4444)
            embed.description = (
                f"Intentaste robar a **{target.mention}** pero te atraparon.\n"
                f"Multa: **{fine:,}** 🪙\n\n"
                f"Tu saldo: **{robber_balance - fine:,}** 🪙"
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
        if len(args) < 2:
            await message.channel.send("❌ Uso: `,removemoney <@usuario> <cantidad>`")
            return
        target = message.mentions[0] if message.mentions else None
        if not target:
            await message.channel.send("❌ Debes mencionar a un usuario. Ej: `,removemoney @usuario 50000`")
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
        cur_bal = await get_balance(str(target.id))
        deduct = min(amount, cur_bal)
        await update_balance(str(target.id), -deduct)
        new_bal = await get_balance(str(target.id))
        embed = discord.Embed(title="💸 Dinero Eliminado", color=0xFF4444)
        embed.description = (
            f"✅ Se eliminaron **{deduct:,}** 🪙 de {target.mention}\n"
            f"📊 Nuevo saldo: **{new_bal:,}** 🪙\n\n"
            f"_Por: {message.author.display_name}_"
        )
        await message.channel.send(embed=embed)

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
        if not args:
            ids = ", ".join(f"`{k}`" for k in FIGHTERS)
            await message.channel.send(f"❌ Uso: `,buyfighter <id>` — IDs: {ids}")
            return
        fid = args[0].lower()
        if fid not in FIGHTERS:
            ids = ", ".join(f"`{k}`" for k in FIGHTERS)
            await message.channel.send(f"❌ ID inválido. IDs válidos: {ids}")
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

    # ,addpuntos <stat> <cantidad>
    elif cmd == "addpuntos":
        await get_or_create_user(user_id, message.author.name)
        if len(args) < 2:
            await message.channel.send("❌ Uso: `,addpuntos <stat> <cantidad>` — Stats: `ataque`, `defensa`, `salud`")
            return
        stat = args[0].lower()
        if stat not in ("ataque", "defensa", "salud"):
            await message.channel.send("❌ Stat inválido. Usa: `ataque`, `defensa` o `salud`.")
            return
        try:
            cantidad = int(args[1])
        except ValueError:
            await message.channel.send("❌ La cantidad debe ser un número entero.")
            return
        if cantidad <= 0:
            await message.channel.send("❌ La cantidad debe ser mayor a 0.")
            return
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT fighter_id FROM fighters WHERE user_id=?", (user_id,)) as cur:
                row = await cur.fetchone()
        if not row:
            await message.channel.send("❌ No tienes luchador. Compra uno con `,buyfighter`.")
            return
        fid = row[0]
        s = await get_fighter_stats(user_id, fid)
        if s["points"] < cantidad:
            await message.channel.send(f"❌ Solo tienes **{s['points']}** puntos disponibles.")
            return
        col_map  = {"ataque": "bonus_attack", "defensa": "bonus_defense", "salud": "bonus_hp"}
        val_map  = {"ataque": cantidad * 2, "defensa": cantidad * 2, "salud": cantidad * 5}
        col = col_map[stat]; bonus_gain = val_map[stat]
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                f"INSERT INTO fighter_levels (user_id, fighter_id, points, {col}) VALUES (?,?,?,?) "
                f"ON CONFLICT(user_id, fighter_id) DO UPDATE SET points=points-?, {col}={col}+?",
                (user_id, fid, -cantidad, bonus_gain, cantidad, bonus_gain)
            )
            await db.commit()
        s2 = await get_fighter_stats(user_id, fid)
        stat_emoji = {"ataque": "⚔️", "defensa": "🛡️", "salud": "❤️"}[stat]
        embed = discord.Embed(title="📈 ¡Stat Mejorado!", color=0x00FF88)
        embed.description = (
            f"{stat_emoji} **{stat.capitalize()}** +{bonus_gain} puntos de stat\n"
            f"🎯 Puntos restantes: **{s2['points']}**\n\n"
            f"**Stats actuales de {s2['name']}:**\n"
            f"❤️ HP: **{s2['hp']}** | ⚔️ ATK: **{s2['attack']}** | 🛡️ DEF: **{s2['defense']}**"
        )
        await message.channel.send(embed=embed)

    # ,ftorneo — torneo de luchadores
    elif cmd == "ftorneo":
        await get_or_create_user(user_id, message.author.name)
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT fighter_id FROM fighters WHERE user_id = ?", (user_id,)) as cur:
                row = await cur.fetchone()
        if not row:
            await message.channel.send("❌ Necesitas un luchador para organizar un torneo. Compra uno con `,buyfighter`.")
            return
        view = FighterTournamentView(host_id=user_id, host_name=message.author.display_name)
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


    # ,balance / ,bal / ,saldo
    elif cmd in ("balance", "bal", "saldo"):
        await get_or_create_user(user_id, message.author.name)
        bal = await get_balance(user_id)
        bank_bal = await get_bank(user_id)
        total = bal + bank_bal
        embed = discord.Embed(title="💰 Tu Saldo", color=0xFFD700)
        embed.add_field(name="👛 Cartera", value=f"**{bal:,}** 🪙", inline=True)
        embed.add_field(name="🏦 Banco", value=f"**{bank_bal:,}** 🪙", inline=True)
        embed.add_field(name="📊 Total", value=f"**{total:,}** 🪙", inline=True)
        embed.set_footer(text=f"Casino Bot • {message.author.name} • El banco es seguro contra robos")
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
        if not args:
            ids = ", ".join(f"`{k}`" for k in SHOP_ITEMS.keys())
            await message.channel.send(f"❌ Uso: `,buy <item_id>`\nIDs disponibles: {ids}")
            return
        item = normalize_shop_item_id(args[0])
        if item not in SHOP_ITEMS:
            ids = ", ".join(f"`{k}`" for k in SHOP_ITEMS.keys())
            await message.channel.send(f"❌ Objeto no encontrado. IDs válidos: {ids}")
            return
        item_data = SHOP_ITEMS[item]
        bal = await get_balance(user_id)
        if bal < item_data["price"]:
            embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
            embed.description = f"Necesitas **{item_data['price']:,}** 🪙 y tienes **{bal:,}** 🪙."
            await message.channel.send(embed=embed)
            return
        await update_balance(user_id, -item_data["price"])
        await add_to_inventory(user_id, item)
        new_balance = await get_balance(user_id)
        embed = discord.Embed(title="🛍️ ¡Compra Exitosa!", color=0x00FF88)
        desc = (
            f"Compraste **{item_data['name']}**.\n{item_data['description']}\n\n"
            f"Gastaste: **{item_data['price']:,}** 🪙\nSaldo restante: **{new_balance:,}** 🪙"
        )
        if item_data["category"] == "rol":
            desc += "\n\n💡 Usa `,collect` para reclamar tus ganancias de rol."
        embed.description = desc
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
        item = normalize_shop_item_id(args[0])
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
        if item_data["category"] == "decorativo":
            flavor = USE_FLAVOR.get(item, f"Usas **{item_data['name']}**.")
            embed = discord.Embed(title=f"✨ Usando {item_data['name']}", color=0x9B59B6)
            embed.description = flavor
            embed.set_footer(text=f"Tienes {qty} en tu inventario")
            await message.channel.send(embed=embed)
        elif item == "anti_rob":
            now_dt = datetime.utcnow()
            shield_exp = now_dt + timedelta(minutes=90)
            await remove_from_inventory(user_id, "anti_rob")
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE users SET shield_until = ? WHERE user_id = ?", (shield_exp.isoformat(), user_id))
                await db.commit()
            embed = discord.Embed(title="🛡️ ¡Escudo Anti-Robos Activado!", color=0x3498DB)
            embed.description = (
                f"🔒 Estás protegido de robos durante **1 hora y 30 minutos**.\n\n"
                f"⏰ Expira a las **{shield_exp.strftime('%H:%M UTC')}**\n"
                f"📦 Escudos restantes: **{qty - 1}**"
            )
            await message.channel.send(embed=embed)
        else:
            embed = discord.Embed(title="❌ No usable", color=0xFF4444)
            embed.description = f"**{item_data['name']}** no se puede usar manualmente.\nUsa `,collect` si es un rol."
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
        tipo_raw = args[0].lower().strip() if args else "comun"
        pack_key = _PACK_ALIASES.get(tipo_raw)
        if not pack_key:
            lines = "\n".join(
                f"{pt['emoji']} `,abrirpaquete {k}` — {pt['label']} · **{pt['price']:,}** 🪙"
                for k, pt in PACK_TYPES.items()
            )
            embed = discord.Embed(title="❌ Tipo de sobre inválido", color=0xFF4444,
                                   description=f"Tipos disponibles:\n{lines}")
            await message.channel.send(embed=embed)
            return
        pt = PACK_TYPES[pack_key]
        bal = await get_balance(user_id)
        if bal < pt["price"]:
            embed = discord.Embed(title="❌ Saldo Insuficiente", color=0xFF4444)
            embed.description = (
                f"{pt['emoji']} **{pt['label']}** cuesta **{pt['price']:,}** 🪙. "
                f"Tienes **{bal:,}** 🪙."
            )
            await message.channel.send(embed=embed)
            return
        await update_balance(user_id, -pt["price"])
        drawn = _draw_pack_cards(pack_key)
        for cid in drawn:
            await _add_card(user_id, cid)
        best_rarity = min((FOOTBALL_CARDS[cid]["rarity"] for cid in drawn),
                          key=lambda r: RARITY_CONFIG[r]["weight"])
        color = RARITY_CONFIG[best_rarity]["color"]
        rc = RARITY_CONFIG[best_rarity]
        title = (f"{rc['emoji']} {pt['label']} — ¡{rc['label']}!"
                 if rc["weight"] <= 4 else f"{pt['emoji']} {pt['label']} abierto")
        embed = discord.Embed(title=title, color=color)
        embed.description = f"**{message.author.display_name}** abrió un **{pt['label']}** y obtuvo:\n\n"
        embed.description += "\n".join(f"➤ {_card_line(cid)}" for cid in drawn)
        new_bal = await get_balance(user_id)
        embed.set_footer(text=f"💰 Saldo restante: {new_bal:,} 🪙")
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
        listing = await _market_get_listing(lid)
        if not listing:
            await message.channel.send(f"❌ La publicación **#{lid}** no existe.")
            return
        _lid, seller_id, card_id, price, ts = listing
        if seller_id != user_id:
            await message.channel.send("❌ Esa publicación no es tuya.")
            return
        await _market_delete_listing(_lid)
        await _add_card(user_id, card_id)
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


if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: Falta la variable de entorno DISCORD_TOKEN")
        exit(1)
    client.run(TOKEN)
