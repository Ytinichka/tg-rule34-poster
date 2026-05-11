import os
import time
import sqlite3
import requests
import logging
import random
from telebot import TeleBot
from telebot.types import InputMediaPhoto

# --- CONFIGURATION ---
API_TOKEN = '8377961270:AAH-_rO-Cctf941gKqr-g6D7rARaHzbG-sU'
CHANNEL_ID = -1002076948442
FETCH_INTERVAL = 1200      # 20 минут
POST_COUNT = 3             # 2-3 — оптимально

# Rule34 Auth
USER_ID = '6222375'
API_KEY = 'dacf53b6d570b01887ef9cb20694d768c7d9d980de1189f458e1e9400f518e88ab980a7cc2b8ae89f5c8d4d64e37524aaa922d824bdf6aba8c6ee20a8d2d0414'

API_URL = "https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&json=1"
BASE_TAGS = "my_hero_academia rating:explicit 1girl ai_generated female -male -2boys -3boys -multiple_boys -futanari -futa -futadom -dickgirl -newhalf -intersex -trap -femboy -yaoi -gay -male_on_male -gay_sex -shemale -tomoko -mineta -sketch -lineart -traditional_media -monochrome -pencil -greyscale -inked -line_art -rough_sketch -comic -manga -doujinshi"

# Персонажи
CHARACTER_DATA = [
    {"name": "Mirko",      "tags": "mirko rumi_usagiyama",     "hashtags": "#Mirko #RumiUsagiyama"},
    {"name": "Uraraka",    "tags": "ochaco_uraraka",           "hashtags": "#Uraraka #OchacoUraraka"},
    {"name": "Toga",       "tags": "himiko_toga",              "hashtags": "#Toga #HimikoToga"},
    {"name": "Jiro",       "tags": "kyoka_jiro",               "hashtags": "#Jiro #KyokaJiro"},
    {"name": "Momo",       "tags": "momo_yaoyorozu",           "hashtags": "#Momo #MomoYaoyorozu"},
    {"name": "Tsuyu",      "tags": "tsuyu_asui",               "hashtags": "#Tsuyu #TsuyuAsui"},
    {"name": "Mt Lady",    "tags": "mt_lady yu_takeyama",      "hashtags": "#MtLady #YuTakeyama"},
    {"name": "Midnight",   "tags": "midnight nemuri_kayama",   "hashtags": "#Midnight #NemuriKayama"},
    {"name": "Ryukyu",     "tags": "ryukyu ryuuko_tatsuma",    "hashtags": "#Ryukyu"},
    {"name": "Nejire",     "tags": "nejire_hado",              "hashtags": "#Nejire #NejireHado"},
]

current_character_index = 0

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = TeleBot(API_TOKEN)

def init_db():
    db_dir = os.getenv('DB_PATH', '.')
    db_path = os.path.join(db_dir, 'posted_arts.db')
    os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Создаём таблицу с нужными колонками
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posted (
            id INTEGER PRIMARY KEY,
            character TEXT,
            posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn

def is_posted(conn, art_id):
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM posted WHERE id = ?', (art_id,))
    return cursor.fetchone() is not None

def mark_as_posted(conn, art_id, character="Unknown"):
    try:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO posted (id, character) VALUES (?, ?)', (art_id, character))
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка записи в БД: {e}")

def fetch_random_arts(conn, character_tags):
    try:
        random_pid = random.randint(0, 900)
        full_tags = f"{BASE_TAGS} {character_tags}"
        
        url = f"{API_URL}&tags={full_tags}&limit=50&pid={random_pid}&user_id={USER_ID}&api_key={API_KEY}"
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        if not response.text or response.text.strip().startswith('"'):
            return []

        data = response.json()
        if not data or not isinstance(data, list):
            return []

        random.shuffle(data)

        to_post = []
        for art in data:
            if is_posted(conn, art['id']):
                continue
            img_url = art.get('sample_url') or art.get('file_url')
            if img_url and img_url.startswith('http'):
                to_post.append(art)
            if len(to_post) == POST_COUNT:
                break
                
        return to_post
    except Exception as e:
        logger.error(f"Ошибка при получении артов: {e}")
        return []

def main():
    global current_character_index
    logger.info("Бот запущен — цикл по персонажам MHA")
    db_conn = init_db()

    while True:
        char = CHARACTER_DATA[current_character_index]
        character_name = char["name"]
        character_hashtags = char["hashtags"]
        
        logger.info(f"→ Ищу арты для: {character_name}")

        to_post = fetch_random_arts(db_conn, char["tags"])

        if to_post:
            caption = f"{character_name} {character_hashtags}\n#MyHeroAcademia #Rule34"
            posted_successfully = False

            try:
                # Пробуем отправить альбомом
                media = []
                for i, art in enumerate(to_post):
                    img_url = art.get('sample_url') or art.get('file_url')
                    if i == 0:
                        media.append(InputMediaPhoto(img_url, caption=caption))
                    else:
                        media.append(InputMediaPhoto(img_url))

                bot.send_media_group(CHANNEL_ID, media)
                logger.info(f"✅ Альбом отправлен ({len(to_post)} артов) — {character_name}")
                posted_successfully = True

            except Exception as e:
                logger.error(f"Ошибка при отправке альбома: {e}. Пробую по одному...")
                
                # Fallback — отправляем по одному
                for art in to_post:
                    try:
                        img_url = art.get('sample_url') or art.get('file_url')
                        bot.send_photo(CHANNEL_ID, img_url, caption=caption)
                        logger.info(f"Отправлен по одному: {art['id']}")
                        posted_successfully = True
                        time.sleep(1.2)
                    except Exception as e2:
                        logger.error(f"Не удалось отправить {art['id']}: {e2}")

            # Отмечаем как запощённые ТОЛЬКО если хотя бы что-то отправилось
            if posted_successfully:
                for art in to_post:
                    mark_as_posted(db_conn, art['id'], character_name)

        else:
            logger.info(f"Не нашёл новые арты для {character_name}, пробую другую страницу...")
            time.sleep(4)
            continue

        # Переключаемся на следующего персонажа
        current_character_index = (current_character_index + 1) % len(CHARACTER_DATA)
        logger.info(f"→ Следующий персонаж: {CHARACTER_DATA[current_character_index]['name']}")
        time.sleep(FETCH_INTERVAL)

if __name__ == "__main__":
    main()
