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
# Упростили базовые теги, чтобы не перегружать запрос и находить больше артов
BASE_TAGS = "my_hero_academia rating:explicit 1girl -male -futanari -futa -trap -sketch -lineart -monochrome"

CHARACTER_DATA = [
    {
        "name": "Mirko",
        "tags": "mirko_(my_hero_academia)",
        "hashtags": "#Mirko #RumiUsagiyama"
    },
    {
        "name": "Uraraka",
        "tags": "uraraka_ochako",
        "hashtags": "#Uraraka #OchacoUraraka"
    },
    {
        "name": "Toga",
        "tags": "toga_himiko",
        "hashtags": "#Toga #HimikoToga"
    },
    {
        "name": "Jiro",
        "tags": "jirou_kyouka",
        "hashtags": "#Jiro #KyokaJiro"
    },
    {
        "name": "Momo",
        "tags": "yaoyorozu_momo",
        "hashtags": "#Momo #MomoYaoyorozu"
    },
    {
        "name": "Tsuyu",
        "tags": "asui_tsuyu",
        "hashtags": "#Tsuyu #TsuyuAsui"
    },
    {
        "name": "MtLady",
        "tags": "mount_lady",
        "hashtags": "#MtLady #YuTakeyama"
    },
    {
        "name": "Midnight",
        "tags": "midnight_(my_hero_academia)",
        "hashtags": "#Midnight #NemuriKayama"
    },
    {
        "name": "Ryukyu",
        "tags": "ryukyu_(my_hero_academia)",
        "hashtags": "#Ryukyu #RyuukoTatsuma"
    },
    {
        "name": "Nejire",
        "tags": "hadou_nejire",
        "hashtags": "#Nejire #NejireHado"
    }
]

current_character_index = 0 # Start with the first character 

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Bot
bot = TeleBot(API_TOKEN)

def init_db():
    db_dir = os.getenv('DB_PATH', '.')
    db_path = os.path.join(db_dir, 'posted_arts.db')
    
    # Создаём папку, если её нет
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

def fetch_random_arts(conn, character_tags):
    try:
        # Сначала пробуем найти на первых страницах (самые свежие и релевантные)
        # Если не находим, пробуем случайную страницу, но в меньшем диапазоне
        pid_choice = random.choice([0, 1, 2, random.randint(0, 100)])
        url = f"{API_URL}&tags={BASE_TAGS} {character_tags}&limit=100&pid={pid_choice}&user_id={USER_ID}&api_key={API_KEY}"
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Rule34 иногда возвращает пустую строку или ошибку в виде строки
        if not response.text or response.text.strip().startswith('"'):
            logger.warning(f"Сайт вернул странный ответ: {response.text}")
            return []
            
        data = response.json()
        if not data or not isinstance(data, list):
            return []
            
        random.shuffle(data)
        
        to_post = []
        for art in data:
            art_id = art['id']
            if not is_posted(conn, art_id):
                # Проверяем наличие URL картинки
                img_url = art.get('sample_url') or art.get('file_url')
                if img_url:
                    to_post.append(art)
                if len(to_post) == POST_COUNT:
                    break
        return to_post
    except Exception as e:
        logger.error(f"Ошибка при получении данных с Rule34: {e}")
        return []

def main():
    global current_character_index
    logger.info("Бот запущен на базе Rule34 с авторизацией (архивный режим)...")
    db_conn = init_db()
    
    while True:
        current_character = CHARACTER_DATA[current_character_index]
        character_name = current_character["name"]
        character_tags = current_character["tags"]
        character_hashtags = current_character["hashtags"]
        logger.info(f"Ищу арты для персонажа: {character_name} с тегами: {character_tags}...")
        to_post = fetch_random_arts(db_conn, character_tags)
        
        if to_post:
            try:
                media = []
                for art in to_post:
                    # Используем sample_url для надежности отправки
                    img_url = art.get('sample_url') or art.get('file_url')
                    media.append(InputMediaPhoto(img_url))
                
                if media:
                    # В telebot подпись для альбома ставится в первый элемент медиа-группы
                    media[0].caption = character_hashtags
                    bot.send_media_group(CHANNEL_ID, media)
                    for art in to_post:
                        mark_as_posted(db_conn, art['id'])
                    logger.info(f"Опубликовано {len(media)} артов.")
                
            except Exception as e:
                logger.error(f"Ошибка при отправке альбома: {e}. Пробую по одному...")
                for art in to_post:
                    try:
                        img_url = art.get('sample_url') or art.get('file_url')
                        bot.send_photo(CHANNEL_ID, img_url, caption=character_hashtags)
                        mark_as_posted(db_conn, art['id'])
                        time.sleep(1)
                    except Exception as e2:
                        logger.error(f"Не удалось отправить арт {art['id']}: {e2}")
        else:
            logger.info("Не удалось найти новые арты на этой странице, попробую другую через 4 сек...")
            time.sleep(4)
            continue
            
        logger.info(f"Сплю {FETCH_INTERVAL} секунд...")
        current_character_index = (current_character_index + 1) % len(CHARACTER_DATA)
        time.sleep(FETCH_INTERVAL)

if __name__ == "__main__":
    main()
