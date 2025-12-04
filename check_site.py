import os
import requests
import json
from bs4 import BeautifulSoup

# --- 1. Конфигурация ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_IDS_STRING = os.environ.get('CHAT_IDS') 
DATA_FILE = "last_data.json"
BASE_DOMAIN = "https://partner.mod.gov.ua"

# Налаштування сторінок
PAGES = {
    "Матеріальне забезпечення": {
        "url": "https://partner.mod.gov.ua/useful-info/material-support-specs",
        "selector": "a.useful-item",
        "type": "standard",
        "check_removed": True  # Тут нам ВАЖЛИВО знати, якщо щось видалили
    },
    "Нормативно-правові акти": {
        "url": "https://partner.mod.gov.ua/useful-info/legal-acts",
        "selector": "a.useful-item",
        "type": "standard",
        "check_removed": True
    },
    "Оголошення": {
        "url": "https://partner.mod.gov.ua/announcements",
        "selector": "a.announcement-card",
        "type": "announcement",
        "check_removed": False # <--- ТУТ МИ ІГНОРУЄМО ВИДАЛЕННЯ (бо це пагінація)
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
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select(css_selector)
        
        print(f"   Found {len(items)} items.")
        
        current_data = []
        for item in items:
            text = ""
            href = item.get('href')

            if page_type == "announcement":
                excerpt = item.select_one('.announcement-card__excerpt')
                text = excerpt.get_text(strip=True) if excerpt else item.get_text(strip=True)
            else:
                text = item.get_text(strip=True)

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
    return f"{item['text']} - {item['url']}"

def send_telegram_notification(message):
    if not CHAT_IDS_STRING:
        print("⚠️ Error: CHAT_IDS is missing.")
        return

    chat_id_list = CHAT_IDS_STRING.split(',')
    print(f"📨 Sending notification...")

    for chat_id in chat_id_list:
        chat_id = chat_id.strip()
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": True
        }
        try:
            requests.post(url, json=payload)
        except Exception:
            pass

def main():
    print("🚀 Starting check script...")
    if not all([BOT_TOKEN, CHAT_IDS_STRING]):
        print("❌ Error: Missing secrets.")
        return

    global_data = get_last_data()
    any_changes_detected = False 
    
    for page_name, settings in PAGES.items():
        print(f"\n🔍 Checking: {page_name}")
        
        page_url = settings['url']
        page_selector = settings['selector']
        page_type = settings.get('type', 'standard')
        should_check_removed = settings.get('check_removed', True)
        
        old_page_data = global_data.get(page_url, [])
        new_page_data = fetch_page_data(page_url, page_selector, page_type)
        
        if new_page_data is None: continue 

        # --- НОВА ЛОГІКА ПОРІВНЯННЯ (ЗБЕРІГАЄМО ПОРЯДОК) ---
        
        # Створюємо набір "старих" записів для швидкого пошуку
        old_set = set(json.dumps(d, sort_keys=True) for d in old_page_data)
        new_set = set(json.dumps(d, sort_keys=True) for d in new_page_data)

        # 1. Шукаємо ДОДАНІ (зберігаючи порядок як на сайті)
        added_items = []
        for item in new_page_data:
            item_json = json.dumps(item, sort_keys=True)
            # Якщо цього елемента немає в старій базі -> він новий
            if item_json not in old_set:
                added_items.append(item)

        # 2. Шукаємо ВИДАЛЕНІ (тільки якщо дозволено)
        removed_items = []
        if should_check_removed:
            for item in old_page_data:
                item_json = json.dumps(item, sort_keys=True)
                if item_json not in new_set:
                    removed_items.append(item)
        
        # Оновлюємо базу даних актуальним станом сторінки
        global_data[page_url] = new_page_data

        # Формуємо звіт
        if added_items or removed_items:
            any_changes_detected = True
            print(f"❗ Changes found on {page_name}!")
            
            message_parts = [f"🔔 **{page_name}**\n"]
            
            if added_items:
                message_parts.append("✅ **Нове:**")
                for item in added_items:
                    message_parts.append(f"{format_item(item)}\n")
            
            if removed_items:
                message_parts.append("❌ **Видалено:**")
                for item in removed_items:
                    message_parts.append(f"{format_item(item)}\n")
            
            final_message = "\n".join(message_parts)
            
            if len(final_message) > 4000:
                final_message = f"🔔 **{page_name}**\n\nБагато змін. Гляньте сайт: {page_url}"
            
            send_telegram_notification(final_message)
        else:
            print(f"   No changes.")

    set_new_data(global_data)

    if not any_changes_detected:
        print("\n💤 No changes anywhere.")
        send_telegram_notification("👌 Перевірка завершена. Все тихо.")

    print("\n🏁 Check finished.")

if __name__ == "__main__":
    main()