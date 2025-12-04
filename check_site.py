import os
import requests
import json
from bs4 import BeautifulSoup

# --- 1. Конфигурация ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_IDS_STRING = os.environ.get('CHAT_IDS') 
DATA_FILE = "last_data.json"
# Список страниц для проверки: "Название для отчета": "URL"
# МИ ДОДАЛИ ТРЕТЮ СТОРІНКУ СЮДИ 👇
PAGES = {
    "Матеріальне забезпечення (Специфікації)": "https://partner.mod.gov.ua/useful-info/material-support-specs",
    "Нормативно-правові акти": "https://partner.mod.gov.ua/useful-info/legal-acts",
    "Оголошення": "https://partner.mod.gov.ua/announcements"
}
def get_last_data():
    """Читает старые данные. Ожидает словарь."""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return {}
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def set_new_data(data):
    """Сохраняет словарь с данными всех страниц."""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Global data file updated.")

def fetch_page_data(url):
    """Скачивает и парсит конкретный URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        # Селектор a.useful-item стандартний для цього сайту
        links = soup.select("a.useful-item")
        
        current_data = []
        for link in links:
            current_data.append({
                "text": link.get_text(strip=True),
                "url": link.get('href')
            })
        return current_data
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def format_item(item):
    url = item['url'].replace('https://partner.mod.gov.ua', '')
    return f"[{item['text']}]({url})"

def send_telegram_notification(message):
    if not CHAT_IDS_STRING:
        print("Error: CHAT_IDS secret is not set.")
        return

    chat_id_list = CHAT_IDS_STRING.split(',')
    for chat_id in chat_id_list:
        chat_id = chat_id.strip() 
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        try:
            requests.post(url, json=payload)
        except Exception as e:
            print(f"Failed to send to {chat_id}: {e}")

def main():
    print("Starting check...")
    if not all([BOT_TOKEN, CHAT_IDS_STRING]):
        print("Error: Missing keys.")
        return

    global_data = get_last_data()
    any_changes_detected = False 
    
    # Проходимо по кожній сторінці зі списку PAGES
    for page_name, page_url in PAGES.items():
        print(f"Checking: {page_name}...")
        
        old_page_data = global_data.get(page_url, [])
        new_page_data = fetch_page_data(page_url)
        
        if new_page_data is None:
            continue 

        old_set = set(json.dumps(d, sort_keys=True) for d in old_page_data)
        new_set = set(json.dumps(d, sort_keys=True) for d in new_page_data)

        added_items_json = new_set - old_set
        removed_items_json = old_set - new_set
        
        global_data[page_url] = new_page_data

        if added_items_json or removed_items_json:
            any_changes_detected = True
            print(f"Changes found on {page_name}!")
            
            added_items = [json.loads(s) for s in added_items_json]
            removed_items = [json.loads(s) for s in removed_items_json]
            
            message_parts = [f"🔔 **Зміни: {page_name}**\n"]

            if added_items:
                message_parts.append("✅ **Додано:**")
                for item in added_items:
                    message_parts.append(f"• {format_item(item)}")
                message_parts.append("\n") 

            if removed_items:
                message_parts.append("❌ **Видалено:**")
                for item in removed_items:
                    message_parts.append(f"• {format_item(item)}")
                message_parts.append("\n")

            message_parts.append(f"[Відкрити сторінку]({page_url})")
            
            final_message = "\n".join(message_parts)
            
            if len(final_message) > 4096:
                final_message = f"🔔 **{page_name}**\n\nякась помилка.\n[Посилання]({page_url})"
            
            send_telegram_notification(final_message)
        else:
            print(f"No changes on {page_name}.")

    set_new_data(global_data)

    if not any_changes_detected:
        print("Перевірка завершена. Змін не було виявлено")
        # Повідомлення про відсутність змін