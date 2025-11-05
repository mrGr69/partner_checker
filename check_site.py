import os
import requests
import json
from bs4 import BeautifulSoup

# --- 1. Конфигурация: Берем из "GitHub Secrets" ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
PAGE_URL = "https://partner.mod.gov.ua/useful-info/material-support-specs"

# Файл, где хранится ПОЛНЫЙ список данных с прошлого раза
DATA_FILE = "last_data.json"

def get_last_data():
    """Читает старые данные из JSON-файла."""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Если файл не найден или пуст, возвращаем пустой список
        print("Data file not found or empty, running for the first time.")
        return []

def set_new_data(data):
    """Сохраняет новые данные в JSON-файл."""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("New data saved to file.")

def fetch_page_data():
    """Скачивает и парсит страницу, возвращая список словарей."""
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
        "parse_mode": "Markdown",
        "disable_web_page_preview": True # Чтобы ссылки не создавали превью
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        print(f"Error sending Telegram message: {response.text}")
    else:
        print("Telegram notification sent.")

def format_item(item):
    """Форматирует элемент для Telegram-сообщения."""
    # Убираем базовый URL, если он есть, для краткости
    url = item['url'].replace('https://partner.mod.gov.ua', '')
    return f"[{item['text']}]({url})"

# --- 3. Основной код ---
def main():
    print("Starting check...")
    if not all([BOT_TOKEN, CHAT_ID]):
        print("Error: Missing BOT_TOKEN or CHAT_ID env variables.")
        return

    try:
        # Шаг 1: Получаем старые и новые данные
        old_data = get_last_data()
        new_data = fetch_page_data()

        if not new_data:
            print("Could not find any data on the page.")
            return

        # Шаг 2: Сравниваем. 
        # Превращаем списки во множества (set) для быстрого сравнения.
        # Используем json.dumps, чтобы словари можно было сравнивать
        old_set = set(json.dumps(d, sort_keys=True) for d in old_data)
        new_set = set(json.dumps(d, sort_keys=True) for d in new_data)

        # Находим добавленные и удаленные
        added_items_json = new_set - old_set
        removed_items_json = old_set - new_set

        # Конвертируем обратно в словари
        added_items = [json.loads(s) for s in added_items_json]
        removed_items = [json.loads(s) for s in removed_items_json]

        # Шаг 3: Формируем отчет
        if not added_items and not removed_items:
            print("No changes detected.")
            return

        print("Changes DETECTED! Building notification.")
        
        message_parts = [
            "🔔 **Обновление на сайте Минобороны!**\n"
        ]

        if added_items:
            message_parts.append("✅ **Добавлено:**")
            for item in added_items:
                message_parts.append(f"• {format_item(item)}")
            message_parts.append("\n") # Пустая строка для разделения

        if removed_items:
            message_parts.append("❌ **Удалено:**")
            for item in removed_items:
                message_parts.append(f"• {format_item(item)}")
            message_parts.append("\n")

        message_parts.append(f"[Перейти на страницу]({PAGE_URL})")
        
        final_message = "\n".join(message_parts)

        # Шаг 4: Отправляем и сохраняем
        send_telegram_notification(final_message)
        set_new_data(new_data) # Сохраняем НОВЫЙ список в файл

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