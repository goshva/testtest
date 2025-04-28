import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
import json
import os

class SteamMarketMonitor:
    def __init__(self):
        self.config = self.load_config()
        self.items = self.config.get('items_to_track', [])
        self.check_interval = self.config.get('check_interval', 3600)
        self.output_file = self.config.get('output_file', 'steam_prices.xlsx')
        self.history_file = self.config.get('history_file', 'price_history.json')
        self.price_history = self.load_history()
        
        # Инициализация файла с заголовками если его нет
        if not os.path.exists(self.output_file):
            with pd.ExcelWriter(self.output_file, engine='openpyxl') as writer:
                pd.DataFrame(columns=['Item', 'Price', 'Timestamp', 'Change']).to_excel(writer, index=False)

    def load_config(self):
        """Загружаем конфигурацию из файла"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            default_config = {
                'items_to_track': [
                    'AK-47 | Redline (Field-Tested)',
                    'AWP | Asiimov (Field-Tested)'
                ],
                'check_interval': 3600,
                'output_file': 'steam_prices.xlsx',
                'history_file': 'price_history.json'
            }
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4)
            return default_config

    def load_history(self):
        """Загружаем историю цен"""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_history(self):
        """Сохраняем историю цен"""
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.price_history, f, indent=4)

    def get_steam_market_price(self, item_name):
        """Получаем текущую цену предмета на Steam Market"""
        url = f"https://steamcommunity.com/market/priceoverview/?appid=730&currency=1&market_hash_name={item_name}"
        
        try:
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            data = response.json()
            
            if data.get('success') and 'lowest_price' in data:
                price = float(data['lowest_price'].replace('$', '').strip())
                return price
            return None
        except Exception as e:
            print(f"Ошибка при получении цены для {item_name}: {e}")
            return None

    def check_price_changes(self):
        """Проверяем изменения цен для всех предметов"""
        current_prices = {}
        changes = []
        
        print(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Начинаем проверку цен...")
        
        for item in self.items:
            price = self.get_steam_market_price(item)
            if price is None:
                continue
                
            current_prices[item] = price
            previous_price = self.price_history.get(item)
            
            if previous_price is not None and previous_price != price:
                change = price - previous_price
                change_percent = (change / previous_price) * 100
                changes.append((item, previous_price, price, change, change_percent))
                print(f"ИЗМЕНЕНИЕ: {item} - было ${previous_price:.2f}, стало ${price:.2f} ({change:+.2f}, {change_percent:+.2f}%)")
            
            self.price_history[item] = price
        
        self.save_history()
        self.update_spreadsheet(current_prices, changes)
        return changes

    def update_spreadsheet(self, current_prices, changes):
        """Обновляем таблицу Excel с текущими ценами"""
        try:
            # Создаем новый DataFrame с текущими данными
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            new_data = []
            
            for item, price in current_prices.items():
                change_info = next((c for c in changes if c[0] == item), None)
                change = change_info[3] if change_info else 0
                
                new_data.append({
                    'Item': item,
                    'Price': price,
                    'Timestamp': timestamp,
                    'Change': change
                })
            
            new_df = pd.DataFrame(new_data)
            
            # Читаем существующие данные и объединяем с новыми
            if os.path.exists(self.output_file):
                try:
                    existing_df = pd.read_excel(self.output_file)
                    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                except Exception as e:
                    print(f"Ошибка при чтении существующего файла, создаем новый: {e}")
                    combined_df = new_df
            else:
                combined_df = new_df
            
            # Сохраняем данные
            with pd.ExcelWriter(self.output_file, engine='openpyxl') as writer:
                combined_df.to_excel(writer, index=False)
            
            print(f"Данные успешно записаны в {self.output_file}")
            
        except Exception as e:
            print(f"Ошибка при обновлении таблицы: {e}")

    def run(self):
        """Запускаем мониторинг"""
        print("Steam Market Monitor запущен")
        print(f"Отслеживаем предметы: {', '.join(self.items)}")
        print(f"Интервал проверки: {self.check_interval} секунд")
        
        try:
            while True:
                self.check_price_changes()
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            print("\nМониторинг остановлен")

if __name__ == "__main__":
    monitor = SteamMarketMonitor()
    monitor.run()