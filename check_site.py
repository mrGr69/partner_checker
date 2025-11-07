import os
import requests
import json
from bs4 import BeautifulSoup

# --- 1. Конфигурация: Берем из "GitHub Secrets" ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_IDS_STRING = os.environ.get('CHAT_IDS') 
PAGE_URL = "https://partner.mod.gov.ua/useful-info/material-support-specs"
DATA_FILE = "last_data.json"

def get_last_data():
    """Читает старые данные из JSON-файла."""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("Data file not found or empty, running for the first time.")
        return []

def set_new_data(data):
    """Сохраняет новые данные в JSON-файЛ."""
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

def format_item(item):
    """Форматирует элемент для Telegram-сообщения."""
    url = item['url'].replace('https://partner.mod.gov.ua', '')
    return f"[{item['text']}]({url})"


def send_telegram_notification(message):
    """Отправляет сообщение во ВСЕ чаты из списка CHAT_IDS."""
    
    if not CHAT_IDS_STRING:
        print("Error: CHAT_IDS secret is not set.")
        return

    chat_id_list = CHAT_IDS_STRING.split(',')
    
    print(f"Sending notification to {len(chat_id_list)} chat(s)...")

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
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                print(f"Successfully sent to {chat_id}")
            else:
                print(f"Error sending to {chat_id}: {response.text}")
        except Exception as e:
            print(f"Failed to send to {chat_id}: {e}")

# --- 3. Основной код (ЗДЕСЬ ГЛАВНЫЕ ИЗМЕНЕНИЯ) ---
def main():
    print("Starting check...")
    if not all([BOT_TOKEN, CHAT_IDS_STRING]):
        print("Error: Missing BOT_TOKEN or CHAT_IDS environment variables.")
        return

    try:
        old_data = get_last_data()
        new_data = fetch_page_data()

        if not new_data:
            print("Could not find any data on the page.")
            return

        old_set = set(json.dumps(d, sort_keys=True) for d in old_data)
        new_set = set(json.dumps(d, sort_keys=True) for d in new_data)

        added_items_json = new_set - old_set
        removed_items_json = old_set - new_set
        
        # --- НОВАЯ ЛОГИКА ---
        if not added_items_json and not removed_items_json:
            # Если изменений нет
            print("No changes detected. Sending 'no changes' notification.")
            final_message = "👌 **Перевірка завершена.**\n\nЗмін на сайті не було виявлено."
            
        else:
            # Если изменения есть
            print("Changes DETECTED! Building notification.")
            
            added_items = [json.loads(s) for s in added_items_json]
            removed_items = [json.loads(s) for s in removed_items_json]
            
            message_parts = [
                "🔔 **Оновлення на сайті partner!**\n"
            ]

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

            message_parts.append(f"[Перейти на сторінку]({PAGE_URL})")
            
            final_message = "\n".join(message_parts)
            
            # if len(final_message) > 4096:
            #     print("Message is too long. Sending truncated message.")
            #     final_message = "🔔 **Оновлення має дуже багато змін**\n\nОбнаружено слишком много изменений. Пожалуйста, проверьте сайт вручную.\n\n" + f"[Перейти на страницу]({PAGE_URL})"

        # --- Отправляем и сохраняем В ЛЮБОМ СЛУЧАЕ ---
        
        # Отправляем сообщение (либо об изменениях, либо об их отсутствии)
        send_telegram_notification(final_message)
        
        # Сохраняем новые данные в файл. 
        # (Если изменений не было, файл просто перезапишется тем же содержимым. 
        # Ваш .yml файл увидит, что файл не изменился, и не будет делать коммит.)
        set_new_data(new_data) 

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