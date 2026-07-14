import asyncio
import json
import os
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import InputPeerChannel, InputPeerUser
from cryptography.fernet import Fernet
import logging

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============== КОНФИГ ==============
BOT_TOKEN = '8351363618:AAHmq7zZSZSeLaylwKjfGzgku1DUlVZuekE'
ADMIN_IDS = [5454585281, 7584816669]
TELEGRAM_SUPPORT_ID = 777000
ENCRYPTION_KEY = b'YOUR_ENCRYPTION_KEY_32_CHARS_HERE'  # Замени на свой ключ (32 символа)
ACCOUNTS_FILE = 'accounts.json'
API_ID = 2040
API_HASH = 'b18441a1ff607e10a989891a5462e627'

# Инициализация
bot = TelegramClient('bot_session', API_ID, API_HASH)

# ============== ШИФРОВАНИЕ ==============
class Encryption:
    @staticmethod
    def generate_key():
        key = Fernet.generate_key()
        with open('.key', 'wb') as f:
            f.write(key)
        return key
    
    @staticmethod
    def load_key():
        if os.path.exists('.key'):
            with open('.key', 'rb') as f:
                return f.read()
        return Encryption.generate_key()
    
    @staticmethod
    def encrypt(text):
        cipher = Fernet(Encryption.load_key())
        return cipher.encrypt(text.encode()).decode()
    
    @staticmethod
    def decrypt(encrypted_text):
        cipher = Fernet(Encryption.load_key())
        return cipher.decrypt(encrypted_text.encode()).decode()

# ============== РАБОТА С JSON ==============
class AccountManager:
    @staticmethod
    def load_accounts():
        if os.path.exists(ACCOUNTS_FILE):
            try:
                with open(ACCOUNTS_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    @staticmethod
    def save_accounts(accounts):
        with open(ACCOUNTS_FILE, 'w') as f:
            json.dump(accounts, f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def add_account(phone, password, twofa_password=None):
        accounts = AccountManager.load_accounts()
        accounts[phone] = {
            'phone': phone,
            'password': Encryption.encrypt(password),
            'twofa_password': Encryption.encrypt(twofa_password) if twofa_password else None,
            'created_at': datetime.now().isoformat()
        }
        AccountManager.save_accounts(accounts)
        return True
    
    @staticmethod
    def get_accounts():
        return AccountManager.load_accounts()
    
    @staticmethod
    def delete_account(phone):
        accounts = AccountManager.load_accounts()
        if phone in accounts:
            del accounts[phone]
            AccountManager.save_accounts(accounts)
            return True
        return False
    
    @staticmethod
    def get_2fa_password(phone):
        accounts = AccountManager.load_accounts()
        if phone in accounts and accounts[phone]['twofa_password']:
            return Encryption.decrypt(accounts[phone]['twofa_password'])
        return None
    
    @staticmethod
    def get_password(phone):
        accounts = AccountManager.load_accounts()
        if phone in accounts:
            return Encryption.decrypt(accounts[phone]['password'])
        return None

# ============== БОТ ==============
@bot.on(events.NewMessage(func=lambda e: e.is_private and e.sender_id in ADMIN_IDS))
async def handler(event):
    sender_id = event.sender_id
    text = event.text.lower()
    
    # Главное меню
    if text == '/start':
        keyboard = [
            [events.Button.inline('➕ Добавить аккаунт', b'add_account')],
            [events.Button.inline('📱 Мои аккаунты', b'my_accounts')]
        ]
        await event.reply('Выбери действие:', buttons=keyboard)
        return
    
    # Добавить аккаунт
    if text.startswith('/add '):
        parts = text.split()
        if len(parts) >= 3:
            phone = parts[1]
            password = parts[2]
            twofa = parts[3] if len(parts) > 3 else None
            
            if AccountManager.add_account(phone, password, twofa):
                await event.reply(f'✅ Аккаунт {phone} добавлен!')
            else:
                await event.reply('❌ Ошибка при добавлении')
        else:
            await event.reply('Использование: /add <телефон> <пароль> [2fa_пароль]')
        return
    
    # Мои аккаунты
    if text == '/accounts':
        accounts = AccountManager.get_accounts()
        if not accounts:
            await event.reply('У тебя нет сохранённых аккаунтов')
            return
        
        msg = '📱 **Твои аккаунты:**\n\n'
        buttons = []
        for i, phone in enumerate(accounts.keys(), 1):
            msg += f'{i}. {phone}\n'
            buttons.append([events.Button.inline(f'☎️ {phone}', f'acc_{phone}'.encode())])
        
        await event.reply(msg, buttons=buttons)
        return

# ============== INLINE КНОПКИ ==============
@bot.on(events.CallbackQuery())
async def callback(event):
    data = event.data.decode()
    sender_id = event.sender_id
    
    if sender_id not in ADMIN_IDS:
        await event.answer('❌ У тебя нет доступа', alert=True)
        return
    
    # Обработка кнопок
    if data.startswith('acc_'):
        phone = data.replace('acc_', '')
        buttons = [
            [events.Button.inline('🔐 Получить пароль', f'pwd_{phone}'.encode())],
            [events.Button.inline('🔑 Получить 2FA', f'2fa_{phone}'.encode())],
            [events.Button.inline('💬 Узнать код поддержки', f'code_{phone}'.encode())],
            [events.Button.inline('🚪 Выйти с аккаунта', f'logout_{phone}'.encode())],
            [events.Button.inline('🗑️ Удалить', f'del_{phone}'.encode())]
        ]
        await event.edit(f'📱 Аккаунт: {phone}', buttons=buttons)
    
    elif data.startswith('pwd_'):
        phone = data.replace('pwd_', '')
        password = AccountManager.get_password(phone)
        await event.answer(f'🔐 Пароль: {password}', alert=True)
    
    elif data.startswith('2fa_'):
        phone = data.replace('2fa_', '')
        twofa = AccountManager.get_2fa_password(phone)
        if twofa:
            await event.answer(f'🔑 2FA пароль: {twofa}', alert=True)
        else:
            await event.answer('❌ 2FA пароль не установлен', alert=True)
    
    elif data.startswith('code_'):
        phone = data.replace('code_', '')
        # Получить последнее сообщение от поддержки
        try:
            messages = await bot.get_messages(TELEGRAM_SUPPORT_ID, limit=1)
            if messages:
                msg_text = messages[0].text
                # Извлечь код (например, "Code: 123456")
                code = msg_text.split()[-1] if 'code' in msg_text.lower() else msg_text
                await event.answer(f'📧 Код: {code}', alert=True)
        except:
            await event.answer('❌ Не удалось получить код', alert=True)
    
    elif data.startswith('logout_'):
        phone = data.replace('logout_', '')
        await event.answer(f'✅ Вы вышли с аккаунта {phone}', alert=True)
        # Можно добавить логику выхода здесь
    
    elif data.startswith('del_'):
        phone = data.replace('del_', '')
        if AccountManager.delete_account(phone):
            await event.answer(f'✅ Аккаунт {phone} удалён', alert=True)
        else:
            await event.answer('❌ Ошибка удаления', alert=True)

# ============== ЗАПУСК ==============
async def main():
    print('🤖 Бот запущен...')
    async with bot:
        await bot.start(bot_token=BOT_TOKEN)
        print('✅ Бот готов к работе!')
        await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
