import os
import requests
import json
from bs4 import BeautifulSoup
import time

# --- 1. Конфигурация ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_IDS_STRING = os.environ.get('CHAT_IDS') 
DATA_FILE = "last_data.json"
BASE_DOMAIN = "https://partner.mod.gov.ua"

# Налаштування для кожної сторінки
PAGES = {
    "Матеріальне забезпечення": {
        "url": "https://partner.mod.gov.ua/useful-info/material-support-specs",
        "selector": "a.useful-item",
        "type": "standard"
    },
    "Нормативно-правові акти": {
        "url": "https://partner.mod.gov.ua/useful-info/legal-acts",
        "selector": "a.useful-item",
        "type": "standard"
    },
    "Оголошення": {
        "url": "https://partner.mod.gov.ua/announcements",
        "selector": "a.announcement-card",
        "type": "announcement" # Спеціальний тип для складної верстки
    }
}

def get_last_data():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list): return {}
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def set_new_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("✅ Global data file updated on disk.")

def fetch_page_data(url, css_selector, page_type):
    print(f"   Downloading {url}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8' # Примусово ставимо UTF-8
        
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select(css_selector)
        
        print(f"   Found {len(items)} items using selector '{css_selector}'")
        
        current_data = []
        for item in items:
            text = ""
            href = item.get('href')

            # --- Логіка парсингу залежно від типу сторінки ---
            if page_type == "announcement":
                # Для оголошень шукаємо текст всередині конкретного <p>
                excerpt = item.select_one('.announcement-card__excerpt')
                if excerpt:
                    text = excerpt.get_text(strip=True)
                else:
                    text = item.get_text(strip=True) # Запасний варіант
            else:
                # Для звичайних списків
                text = item.get_text(strip=True)

            # --- Виправлення посилань ---
            if href and href.startswith('/'):
                href = BASE_DOMAIN + href
            
            if text and href:
                current_data.append({
                    "text": text,
                    "url": href
                })
        
        return current_data
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return None

def format_item(item):
    # Формат: Текст - Посилання
    return f"{item['text']} - {item['url']}"

def send_telegram_notification(message):
    if not CHAT_IDS_STRING:
        print("⚠️ Error: CHAT_IDS secret is not set.")
        return

    chat_id_list = CHAT_IDS_STRING.split(',')
    print(f"📨 Sending Telegram notification to {len(chat_id_list)} chats...")

    for chat_id in chat_id_list:
        chat_id = chat_id.strip()
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": True
        }
        try:
            r = requests.post(url, json=payload)
            if r.status_code == 200:
                print(f"   Sent to {chat_id}: OK")
            else:
                print(f"   Failed to send to {chat_id}: {r.text}")
        except Exception as e:
            print(f"   Exception sending to {chat_id}: {e}")

def main():
    print("🚀 Starting check script...")
    
    # 1. Перевірка змінних
    if not BOT_TOKEN:
        print("❌ Error: BOT_TOKEN is missing!")
        return
    if not CHAT_IDS_STRING:
        print("❌ Error: CHAT_IDS is missing!")
        return

    global_data = get_last_data()
    any_changes_detected = False 
    
    for page_name, settings in PAGES.items():
        print(f"\n🔍 Checking: {page_name}")
        
        page_url = settings['url']
        page_selector = settings['selector']
        page_type = settings.get('type', 'standard')
        
        old_page_data = global_data.get(page_url, [])
        new_page_data = fetch_page_data(page_url, page_selector, page_type)
        
        if new_page_data is None: 
            print("   Skipping comparison due to fetch error.")
            continue 

        # Порівнюємо
        old_set = set(json.dumps(d, sort_keys=True) for d in old_page_data)
        new_set = set(json.dumps(d, sort_keys=True) for d in new_page_data)

        added_items_json = new_set - old_set
        
        # Оновлюємо базу в пам'яті
        global_data[page_url] = new_page_data

        if added_items_json:
            any_changes_detected = True
            print(f"❗ Changes found on {page_name}!")
            
            added_items = [json.loads(s) for s in added_items_json]
            
            # Формуємо повідомлення
            message_parts = [f"🔔 **{page_name}**\n"]
            
            for item in added_items:
                # Додаємо два переноси рядка для відступу
                message_parts.append(f"{format_item(item)}\n") 
            
            final_message = "\n".join(message_parts)
            
            # Обрізка, якщо занадто довге
            if len(final_message) > 4000:
                final_message = f"🔔 **{page_name}**\n\nзабагато ({len(added_items)} шт.).\nПеревірте сайт вручну: {page_url}"
            
            send_telegram_notification(final_message)
        else:
            print(f"   No changes.")

    # Зберігаємо файл
    set_new_data(global_data)

    # Якщо змін не було ніде
    if not any_changes_detected:
        print("\n💤 No changes anywhere.")
        send_telegram_notification("👌 Перевірка завершена. Нових оголошень немає.")

    print("\n🏁 Check finished.")

if __name__ == "__main__":
    main()