import os
import requests
import json
import hashlib
from bs4 import BeautifulSoup

# --- 1. Конфигурация: Берем из "Environment Variables" на Render ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
PAGE_URL = "https://partner.mod.gov.ua/useful-info/material-support-specs"

# Путь, куда Render подключит наш диск. 
# '/data' - это стандартный путь, его и будем использовать.
DATA_PATH = "/data/last_hash.txt"

def get_last_hash():
    """Читает хеш из файла на диске."""
    try:
        with open(DATA_PATH, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        # Если файл не найден (самый первый запуск), это нормально
        print("Hash file not found, creating a new one.")
        return None

def set_new_hash(new_hash):
    """Сохраняет новый хеш в файл на диске."""
    # Убедимся, что директория /data существует (хотя Render ее создаст)
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, 'w') as f:
        f.write(new_hash)

def fetch_page_data():
    """Скачивает и парсит страницу, возвращая список ссылок и текста."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(PAGE_URL, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.select("a.useful-item")
    
    current_data = []
    for link in links:
        current_data.append({
            "text": link.get_text(strip=True),
            "url": link.get('href')
        })
    return current_data

def send_telegram_notification(message):
    """Отправляет сообщение в Telegram."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        print(f"Error sending Telegram message: {response.text}")

def create_hash(data):
    """Создает уникальный 'отпечаток' SHA-256 для списка данных."""
    data_string = json.dumps(data, sort_keys=True)
    return hashlib.sha256(data_string.encode('utf-8')).hexdigest()

# --- 3. Основной код ---
def main():
    print("Starting check...")
    
    if not all([BOT_TOKEN, CHAT_ID]):
        print("Error: Missing BOT_TOKEN or CHAT_ID environment variables.")
        return

    try:
        # Шаг A: Получаем старый хеш из файла
        old_hash = get_last_hash()
        
        # Шаг B: Получаем новые данные с сайта
        new_data = fetch_page_data()
        if not new_data:
            print("Could not find any data on the page.")
            return

        # Шаг C: Сравниваем
        new_hash = create_hash(new_data)
        
        print(f"Old hash: {old_hash}")
        print(f"New hash: {new_hash}")

        if old_hash == new_hash:
            print("No changes detected.")
        else:
            print("Changes DETECTED! Sending notification...")
            # Шаг D: Отправляем уведомление
            message = (
                "🔔 **Обновление на сайте Минобороны!**\n\n"
                "Список спецификаций изменился.\n\n"
                f"[Проверить на сайте]({PAGE_URL})"
            )
            send_telegram_notification(message)
            
            # Шаг E: Сохраняем новый хеш в файл
            set_new_hash(new_hash)
            print("New hash saved to disk.")

    except Exception as e:
        print(f"An error occurred: {e}")
        try:
            send_telegram_notification(f"Ошибка парсера: {e}")
        except:
            pass
            
    finally:
        print("Check finished.")

if __name__ == "__main__":
    main()