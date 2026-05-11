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
BASE_TAGS = "my_hero_academia rating:explicit 1girl ai_generated female -male -2boys -3boys -multiple_boys -futanari -futa -futadom -dickgirl -newhalf -intersex -trap -femboy -yaoi -gay -male_on_male -gay_sex -shemale -tomoko -mineta -sketch -lineart -traditional_media -monochrome -pencil -greyscale -inked -line_art -rough_sketch -comic -manga -doujinshi"

CHARACTER_DATA = [
    {
        "name": "Mirko",
        "tags": "mirko rumi_usagiyama",
        "hashtags": "#Mirko #RumiUsagiyama"
    },
    {
        "name": "Uraraka",
        "tags": "ochaco_uraraka",
        "hashtags": "#Uraraka #OchacoUraraka"
    },
    {
        "name": "Toga",
        "tags": "himiko_toga",
        "hashtags": "#Toga #HimikoToga"
    },
    {
        "name": "Jiro",
        "tags": "kyoka_jiro",
        "hashtags": "#Jiro #KyokaJiro"
    },
    {
        "name": "Momo",
        "tags": "momo_yaoyorozu",
        "hashtags": "#Momo #MomoYaoyorozu"
    },
    {
        "name": "Tsuyu",
        "tags": "tsuyu_asui",
        "hashtags": "#Tsuyu #TsuyuAsui"
    },
    {
        "name": "MtLady",
        "tags": "mt_lady yu_takeyama",
        "hashtags": "#MtLady #YuTakeyama"
    },
    {
        "name": "Midnight",
        "tags": "midnight nemuri_kayama",
        "hashtags": "#Midnight #NemuriKayama"
    },
    {
        "name": "Ryukyu",
        "tags": "ryukyu ryuuko_tatsuma",
        "hashtags": "#Ryukyu #RyuukoTatsuma"
    },
    {
        "name": "Nejire",
        "tags": "nejire_hado",
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
        # На Rule34 берем случайную страницу из архива (до 1000)
        random_pid = random.randint(0, 1000)
        url = f"{API_URL}&tags={BASE_TAGS} {character_tags}&limit=50&pid={random_pid}&user_id={USER_ID}&api_key={API_KEY}"
        
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
                    bot.send_media_group(CHANNEL_ID, media, caption=character_hashtags)
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
            logger.info("Не удалось найти новые арты на этой странице, попробую другую через 10 сек...")
            time.sleep(4)
            continue
            
        logger.info(f"Сплю {FETCH_INTERVAL} секунд...")
        current_character_index = (current_character_index + 1) % len(CHARACTER_DATA)
        time.sleep(FETCH_INTERVAL)

if __name__ == "__main__":
    main()
