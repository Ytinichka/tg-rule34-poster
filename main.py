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
FETCH_INTERVAL = 1200  # 20 минут
POST_COUNT = 5        # 5 артов за раз

# Rule34 Auth
USER_ID = '6222375'
API_KEY = 'dacf53b6d570b01887ef9cb20694d768c7d9d980de1189f458e1e9400f518e88ab980a7cc2b8ae89f5c8d4d64e37524aaa922d824bdf6aba8c6ee20a8d2d0414'

API_URL = "https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&json=1"

# Базовые теги (женский пол, без мужских персонажей и т.д.)
BASE_TAGS = "rating:explicit 1girl ai_generated female -male -2boys -3boys -multiple_boys -futanari -futa -futadom -dickgirl -newhalf -intersex -trap -femboy -yaoi -gay -male_on_male -gay_sex -shemale -tomoko -mineta -sketch -lineart -traditional_media -monochrome -pencil -greyscale -inked -line_art -rough_sketch -comic -manga -doujinshi"

# Список персонажей для циклического постинга
CHARACTERS = [
    "usagiyama_rumi", # Мирко
    "uraraka_ochako", # Урарака
    "yaoyorozu_momo", # Момо
    "ashido_mina",    # Мина
    "asui_tsuyu",     # Тсую
    "jirou_kyouka",   # Джиро
    "toga_himiko",    # Тога
    "hado_nejire",    # Неджире
    "kayama_nemuri",  # Полночь
    "takeyama_yuu"    # Леди Гора
]

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Bot
bot = TeleBot(API_TOKEN)

def init_db():
    db_dir = os.getenv('DB_PATH', '.')
    db_path = os.path.join(db_dir, 'posted_arts.db')
    os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS posted (id INTEGER PRIMARY KEY)')
    conn.commit()
    return conn

def is_posted(conn, art_id):
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM posted WHERE id = ?', (art_id,))
    return cursor.fetchone() is not None

def mark_as_posted(conn, art_id):
    cursor = conn.cursor()
    cursor.execute('INSERT INTO posted (id) VALUES (?)', (art_id,))
    conn.commit()

def format_tags_as_hashtags(tags_string, character_name, limit=15):
    tags = tags_string.split()
    hashtags = []
    for tag in tags:
        clean_tag = tag.replace('(', '').replace(')', '').replace('[', '').replace(']', '')
        if clean_tag:
            hashtags.append("#" + clean_tag)
    
    # Приоритетные хештеги
    important = ['hentai', 'mha', character_name.replace('_', '')]
    result = []
    for imp in important:
        if f"#{imp}" not in [h.lower() for h in result]:
            result.append(f"#{imp}")
            
    for h in hashtags:
        if h.lower() not in [r.lower() for r in result]:
            result.append(h)
    
    return " ".join(result[:limit])

def fetch_arts_by_character(conn, character, pid=None):
    try:
        tags = f"{character} {BASE_TAGS}"
        if pid is None:
            pid = random.randint(0, 50)
            
        url = f"{API_URL}&tags={tags}&limit=50&pid={pid}&user_id={USER_ID}&api_key={API_KEY}"
        
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
            art_id = art['id']
            if not is_posted(conn, art_id):
                img_url = art.get('sample_url') or art.get('file_url')
                if img_url:
                    to_post.append(art)
                if len(to_post) == POST_COUNT:
                    break
        return to_post
    except Exception as e:
        logger.error(f"Ошибка при получении данных для {character} (pid={pid}): {e}")
        return []

def main():
    logger.info("Бот запущен. Режим: циклическая очередь персонажей с умным поиском.")
    db_conn = init_db()
    char_index = 0
    
    while True:
        current_char = CHARACTERS[char_index]
        logger.info(f"--- Очередь: {current_char} ---")
        
        to_post = []
        # Пытаемся найти арты на разных страницах для текущего персонажа
        for attempt in range(1, 11): # Максимум 10 разных страниц
            pid = random.randint(0, 100)
            logger.info(f"Поиск для {current_char}, попытка {attempt} (страница {pid})...")
            to_post = fetch_arts_by_character(db_conn, current_char, pid=pid)
            
            if to_post:
                break
            else:
                logger.info(f"На странице {pid} ничего нового для {current_char}. Жду 3 сек...")
                time.sleep(3)
        
        if to_post:
            try:
                media = []
                for i, art in enumerate(to_post):
                    img_url = art.get('sample_url') or art.get('file_url')
                    if i == 0:
                        raw_tags = art.get('tags', '')
                        caption_text = format_tags_as_hashtags(raw_tags, current_char)
                        media.append(InputMediaPhoto(img_url, caption=caption_text))
                    else:
                        media.append(InputMediaPhoto(img_url))
                
                if media:
                    bot.send_media_group(CHANNEL_ID, media)
                    for art in to_post:
                        mark_as_posted(db_conn, art['id'])
                    logger.info(f"Успешно опубликовано {len(media)} артов с {current_char}.")
                
                # Переходим к следующему персонажу
                char_index = (char_index + 1) % len(CHARACTERS)
                
            except Exception as e:
                logger.error(f"Ошибка при отправке: {e}")
                # В случае ошибки отправки не меняем персонажа, попробуем еще раз через интервал
        else:
            logger.warning(f"Не удалось найти новые арты для {current_char} после 10 попыток. Пропускаем.")
            char_index = (char_index + 1) % len(CHARACTERS)
            # Если ничего не нашли, не ждем полный интервал, переходим к следующему через короткую паузу
            time.sleep(5)
            continue
            
        logger.info(f"Сплю {FETCH_INTERVAL} секунд до следующего персонажа...")
        time.sleep(FETCH_INTERVAL)

if __name__ == "__main__":
    main()
