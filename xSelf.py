"""
xSelf - Telegram Self Bot
یک ربات تلگرام قدرتمند برای مدیریت خودکار اکانت تلگرام

کانال: @xSelfChannel
سازنده: @theesmaeil1

⚠️ نکته مهم:
- شماره تلفن باید با فرمت بین‌المللی وارد شود (مثلاً: +989692842510)
- شماره باید بدون صفر اول و با کد کشور باشد
"""

import asyncio
import os
import random
import logging
from datetime import datetime, timedelta
import pytz
import jdatetime
from pyrogram import Client, enums, filters
from pyrogram.errors import FloodWait, RPCError, UserDeactivated, UserBlocked
from collections import defaultdict
import time
import aiosqlite

# ============================================================================
# تنظیمات
# ============================================================================

# API تنظیمات
# برای دریافت API_ID و API_HASH به https://my.telegram.org بروید
API_ID =   # جایگزین با api_id شما
API_HASH = ''  # جایگزین با api_hash شما

# نام فایل session
SESSION_NAME = 'xSelf'

# تنظیمات لیمیت‌ها برای جلوگیری از فریز اکانت
RATE_LIMITS = {
    'profile_update': {'max_per_hour': 5, 'min_delay': 720},  # حداکثر 5 بار در ساعت، حداقل 12 دقیقه بین هر تغییر
    'message_send': {'max_per_minute': 20, 'min_delay': 3},  # حداکثر 20 پیام در دقیقه، حداقل 3 ثانیه بین هر پیام
    'message_delete': {'max_per_minute': 10, 'min_delay': 6},  # حداکثر 10 حذف در دقیقه، حداقل 6 ثانیه بین هر حذف
    'curse_reply': {'max_per_hour': 10, 'min_delay': 360},  # حداکثر 10 فحش در ساعت، حداقل 6 دقیقه بین هر فحش
    'block_user': {'max_per_hour': 5, 'min_delay': 720},  # حداکثر 5 بلاک در ساعت
    'chat_action': {'min_delay': 2},  # حداقل 2 ثانیه بین هر action
}

# تنظیمات کانال و سازنده
CHANNEL_USERNAME = "xSelfChannel"
DEVELOPER_USERNAME = "theesmaeil1"

# نام فایل دیتابیس
DATABASE_FILE = "xself.db"

# فحش‌های پیش‌فرض
DEFAULT_CURSES = ["کصمادرت", "کصننت", "ننه جنده", "کصمامانت تو ماهیتابه"]

# گروه‌های ذخیره محتوا (Realm Groups)
# ID عددی گروه‌هایی که می‌خواهید تمام پیام‌ها به آن‌ها فوروارد شوند
# برای دریافت ID گروه: در گروه دستور /id را ارسال کنید یا از ربات @userinfobot استفاده کنید
# 
# ⚠️ نکته مهم: برای اینکه پیام‌ها ذخیره شوند:
# 1. ربات را به گروه اضافه کنید
# 2. به ربات دسترسی ارسال پیام بدهید
# 3. از دستور testrealm برای تست دسترسی استفاده کنید
REALM_CHAT_IDS = [
    -1000000000
]

# ============================================================================
# تنظیمات لاگ
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# کلاس دیتابیس
# ============================================================================

class Database:
    def __init__(self, db_file="xself.db"):
        self.db_file = db_file
    
    async def init_db(self):
        """ایجاد جداول دیتابیس"""
        async with aiosqlite.connect(self.db_file) as db:
            # جدول دشمنان
            await db.execute('''
                CREATE TABLE IF NOT EXISTS enemies (
                    user_id INTEGER PRIMARY KEY
                )
            ''')
            
            # جدول کاربران سکوت شده
            await db.execute('''
                CREATE TABLE IF NOT EXISTS muted_users (
                    user_id INTEGER PRIMARY KEY
                )
            ''')
            
            # جدول فحش‌ها
            await db.execute('''
                CREATE TABLE IF NOT EXISTS curses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT UNIQUE NOT NULL
                )
            ''')
            
            # جدول گروه‌های ذخیره محتوا
            await db.execute('''
                CREATE TABLE IF NOT EXISTS realm_chats (
                    chat_id INTEGER PRIMARY KEY
                )
            ''')
            
            await db.commit()
            logger.info("Database initialized successfully")
    
    # توابع دشمنان
    async def add_enemy(self, user_id: int):
        """افزودن دشمن"""
        async with aiosqlite.connect(self.db_file) as db:
            try:
                await db.execute('INSERT OR IGNORE INTO enemies (user_id) VALUES (?)', (user_id,))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error adding enemy: {e}")
                return False
    
    async def remove_enemy(self, user_id: int):
        """حذف دشمن"""
        async with aiosqlite.connect(self.db_file) as db:
            try:
                await db.execute('DELETE FROM enemies WHERE user_id = ?', (user_id,))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error removing enemy: {e}")
                return False
    
    async def get_enemies(self):
        """دریافت لیست دشمنان"""
        async with aiosqlite.connect(self.db_file) as db:
            try:
                async with db.execute('SELECT user_id FROM enemies') as cursor:
                    rows = await cursor.fetchall()
                    return [row[0] for row in rows]
            except Exception as e:
                logger.error(f"Error getting enemies: {e}")
                return []
    
    async def clear_enemies(self):
        """پاکسازی لیست دشمنان"""
        async with aiosqlite.connect(self.db_file) as db:
            try:
                await db.execute('DELETE FROM enemies')
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error clearing enemies: {e}")
                return False
    
    # توابع کاربران سکوت شده
    async def add_muted_user(self, user_id: int):
        """افزودن کاربر به لیست سکوت"""
        async with aiosqlite.connect(self.db_file) as db:
            try:
                await db.execute('INSERT OR IGNORE INTO muted_users (user_id) VALUES (?)', (user_id,))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error adding muted user: {e}")
                return False
    
    async def remove_muted_user(self, user_id: int):
        """حذف کاربر از لیست سکوت"""
        async with aiosqlite.connect(self.db_file) as db:
            try:
                await db.execute('DELETE FROM muted_users WHERE user_id = ?', (user_id,))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error removing muted user: {e}")
                return False
    
    async def get_muted_users(self):
        """دریافت لیست کاربران سکوت شده"""
        async with aiosqlite.connect(self.db_file) as db:
            try:
                async with db.execute('SELECT user_id FROM muted_users') as cursor:
                    rows = await cursor.fetchall()
                    return [row[0] for row in rows]
            except Exception as e:
                logger.error(f"Error getting muted users: {e}")
                return []
    
    async def clear_muted_users(self):
        """پاکسازی لیست کاربران سکوت شده"""
        async with aiosqlite.connect(self.db_file) as db:
            try:
                await db.execute('DELETE FROM muted_users')
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error clearing muted users: {e}")
                return False
    
    # توابع فحش‌ها
    async def add_curse(self, text: str):
        """افزودن فحش"""
        async with aiosqlite.connect(self.db_file) as db:
            try:
                await db.execute('INSERT OR IGNORE INTO curses (text) VALUES (?)', (text,))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error adding curse: {e}")
                return False
    
    async def remove_curse(self, text: str):
        """حذف فحش"""
        async with aiosqlite.connect(self.db_file) as db:
            try:
                await db.execute('DELETE FROM curses WHERE text = ?', (text,))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error removing curse: {e}")
                return False
    
    async def get_curses(self):
        """دریافت لیست فحش‌ها"""
        async with aiosqlite.connect(self.db_file) as db:
            try:
                async with db.execute('SELECT text FROM curses') as cursor:
                    rows = await cursor.fetchall()
                    return [row[0] for row in rows]
            except Exception as e:
                logger.error(f"Error getting curses: {e}")
                return []
    
    async def clear_curses(self):
        """پاکسازی لیست فحش‌ها"""
        async with aiosqlite.connect(self.db_file) as db:
            try:
                await db.execute('DELETE FROM curses')
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error clearing curses: {e}")
                return False
    
    async def init_default_curses(self, default_curses: list):
        """افزودن فحش‌های پیش‌فرض"""
        async with aiosqlite.connect(self.db_file) as db:
            try:
                # بررسی اینکه آیا فحش‌ها وجود دارند
                async with db.execute('SELECT COUNT(*) FROM curses') as cursor:
                    count = (await cursor.fetchone())[0]
                
                if count == 0:
                    # افزودن فحش‌های پیش‌فرض
                    for curse in default_curses:
                        await db.execute('INSERT OR IGNORE INTO curses (text) VALUES (?)', (curse,))
                    await db.commit()
                    logger.info("Default curses initialized")
            except Exception as e:
                logger.error(f"Error initializing default curses: {e}")
    
    # توابع گروه‌های ذخیره محتوا
    async def add_realm_chat(self, chat_id: int):
        """افزودن گروه به لیست ذخیره محتوا"""
        async with aiosqlite.connect(self.db_file) as db:
            try:
                await db.execute('INSERT OR IGNORE INTO realm_chats (chat_id) VALUES (?)', (chat_id,))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error adding realm chat: {e}")
                return False
    
    async def remove_realm_chat(self, chat_id: int):
        """حذف گروه از لیست ذخیره محتوا"""
        async with aiosqlite.connect(self.db_file) as db:
            try:
                await db.execute('DELETE FROM realm_chats WHERE chat_id = ?', (chat_id,))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error removing realm chat: {e}")
                return False
    
    async def get_realm_chats(self):
        """دریافت لیست گروه‌های ذخیره محتوا"""
        async with aiosqlite.connect(self.db_file) as db:
            try:
                async with db.execute('SELECT chat_id FROM realm_chats') as cursor:
                    rows = await cursor.fetchall()
                    return [row[0] for row in rows]
            except Exception as e:
                logger.error(f"Error getting realm chats: {e}")
                return []
    
    async def is_realm_chat(self, chat_id: int):
        """بررسی اینکه آیا گروه در لیست ذخیره محتوا است"""
        async with aiosqlite.connect(self.db_file) as db:
            try:
                async with db.execute('SELECT 1 FROM realm_chats WHERE chat_id = ?', (chat_id,)) as cursor:
                    row = await cursor.fetchone()
                    return row is not None
            except Exception as e:
                logger.error(f"Error checking realm chat: {e}")
                return False

# ============================================================================
# متغیرهای سراسری
# ============================================================================

# ردیابی زمان آخرین عملیات
last_action_time = defaultdict(float)
action_count = defaultdict(int)
action_reset_time = defaultdict(float)

# API تنظیمات
app = Client(SESSION_NAME, API_ID, API_HASH)

# ایجاد دیتابیس
db = Database(DATABASE_FILE)
channel_joined = False  # برای بررسی عضویت در کانال

# ایجاد دایرکتوری downloads اگر وجود نداشته باشد
if not os.path.exists("downloads"):
    os.makedirs("downloads")

# کش برای ذخیره گروه‌های نامعتبر (برای جلوگیری از تلاش‌های مکرر)
invalid_realm_chats = set()

# ============================================================================
# توابع کمکی
# ============================================================================

# تابع بررسی اعتبار گروه
async def is_valid_realm_chat(chat_id: int) -> bool:
    """بررسی اینکه آیا گروه معتبر است و به آن دسترسی داریم"""
    # اگر در لیست invalid است، هر 5 دقیقه یکبار دوباره تلاش می‌کنیم
    if chat_id in invalid_realm_chats:
        # هر 5 دقیقه یکبار دوباره تلاش می‌کنیم
        return False
    
    # بررسی اینکه آیا این ID در REALM_CHAT_IDS است (گروه‌های config را حذف نکن)
    if chat_id in REALM_CHAT_IDS:
        # اگر در config است، همیشه تلاش می‌کنیم
        try:
            await app.get_chat(chat_id)
            # اگر دسترسی پیدا کردیم، از لیست invalid حذفش کن
            invalid_realm_chats.discard(chat_id)
            return True
        except Exception as e:
            # اگر دسترسی نداریم، فقط warning می‌دهیم اما حذف نمی‌کنیم
            if chat_id not in invalid_realm_chats:
                logger.warning(f"⚠️ Realm chat {chat_id} from config is not accessible yet: {e}")
                logger.info(f"   The ID is kept in database. Make sure the bot is a member of this group.")
                invalid_realm_chats.add(chat_id)
            return False
    
    # برای گروه‌های دیگر (که از config نیستند)، رفتار قبلی
    try:
        await app.get_chat(chat_id)
        invalid_realm_chats.discard(chat_id)
        return True
    except Exception as e:
        logger.warning(f"Realm chat {chat_id} is invalid or not accessible: {e}")
        invalid_realm_chats.add(chat_id)
        # حذف از دیتابیس اگر نامعتبر است (فقط برای گروه‌هایی که در config نیستند)
        try:
            await db.remove_realm_chat(chat_id)
            logger.info(f"Removed invalid realm chat {chat_id} from database")
        except:
            pass
        return False

# تابع تلاش مجدد برای دسترسی به گروه
async def retry_realm_access(chat_id: int):
    """تلاش مجدد برای دسترسی به گروه (برای گروه‌های config)"""
    if chat_id in REALM_CHAT_IDS:
        try:
            await app.get_chat(chat_id)
            invalid_realm_chats.discard(chat_id)
            logger.info(f"✅ Successfully accessed realm chat {chat_id}")
            return True
        except Exception as e:
            logger.debug(f"Still cannot access realm chat {chat_id}: {e}")
            return False
        return False

# تابع تلاش مجدد برای دسترسی به گروه
async def retry_realm_access(chat_id: int):
    """تلاش مجدد برای دسترسی به گروه (برای گروه‌های config)"""
    if chat_id in REALM_CHAT_IDS:
        try:
            await app.get_chat(chat_id)
            invalid_realm_chats.discard(chat_id)
            logger.info(f"✅ Successfully accessed realm chat {chat_id}")
            return True
        except Exception as e:
            logger.debug(f"Still cannot access realm chat {chat_id}: {e}")
            return False
    return False

# تابع بررسی لیمیت
async def check_rate_limit(action_type: str, user_id: int = None) -> bool:
    """بررسی لیمیت برای عملیات مختلف"""
    limit_config = RATE_LIMITS.get(action_type, {})
    if not limit_config:
        return True
    
    current_time = time.time()
    key = f"{action_type}_{user_id}" if user_id else action_type
    
    # ریست کردن شمارنده در بازه زمانی مشخص
    reset_interval = 3600  # یک ساعت
    if current_time - action_reset_time[key] > reset_interval:
        action_count[key] = 0
        action_reset_time[key] = current_time
    
    # بررسی تعداد عملیات
    max_count = limit_config.get('max_per_hour') or limit_config.get('max_per_minute', float('inf'))
    if action_count[key] >= max_count:
        logger.warning(f"Rate limit exceeded for {action_type}")
        return False
    
    # بررسی تاخیر بین عملیات
    min_delay = limit_config.get('min_delay', 0)
    if current_time - last_action_time[key] < min_delay:
        wait_time = min_delay - (current_time - last_action_time[key])
        logger.info(f"Rate limit delay: waiting {wait_time:.2f}s for {action_type}")
        await asyncio.sleep(wait_time)
    
    # به‌روزرسانی زمان و شمارنده
    last_action_time[key] = time.time()
    action_count[key] += 1
    return True

# تابع مدیریت خطا با FloodWait
async def safe_execute(func, *args, max_retries=3, **kwargs):
    """اجرای ایمن توابع با مدیریت FloodWait"""
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except FloodWait as e:
            wait_time = min(e.value, 300)  # حداکثر 5 دقیقه انتظار
            logger.warning(f"FloodWait: waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(wait_time)
        except (UserDeactivated, UserBlocked) as e:
            logger.error(f"Account issue: {e}")
            raise
        except RPCError as e:
            logger.error(f"RPC Error: {e}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    return None

# ============================================================================
# هندلرهای پیام
# ============================================================================

# مدیریت عکس‌های تایمردار
@app.on_message(filters.photo & filters.private)
async def onphoto(client, message):
    if message.photo.ttl_seconds:
        rand = random.randint(1000, 9999999)
        local = f"downloads/photo-{rand}.png"
        try:
            await app.download_media(message.photo.file_id, file_name=local)
            if await check_rate_limit('message_send'):
                await safe_execute(
                    app.send_photo,
                    "me",
                    photo=local,
                    caption=f"`🥸 New timed image {message.photo.date} | time: {message.photo.ttl_seconds}s`"
                )
        except Exception as e:
            logger.error(f"Error handling photo: {e}")
        finally:
            if os.path.exists(local):
                os.remove(local)

# مدیریت ویدیوهای تایمردار
@app.on_message(filters.video & filters.private)
async def onvideo(client, message):
    if message.video.ttl_seconds:
        rand = random.randint(1000, 9999999)
        local = f"downloads/video-{rand}.mp4"
        try:
            await app.download_media(message.video.file_id, file_name=local)
            if await check_rate_limit('message_send'):
                await safe_execute(
                    app.send_video,
                    "me",
                    video=local,
                    caption=f"`🥸 New timed video {message.video.date} | time: {message.video.ttl_seconds}s`"
                )
        except Exception as e:
            logger.error(f"Error handling video: {e}")
        finally:
            if os.path.exists(local):
                os.remove(local)

# ذخیره پیام
@app.on_message(filters.reply & filters.regex('(?i)^save$'))
async def save(client, message):
    try:
        if await check_rate_limit('message_send'):
            await safe_execute(app.copy_message, "me", message.chat.id, message.reply_to_message_id)
        if await check_rate_limit('message_delete'):
            await safe_execute(app.delete_messages, message.chat.id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error in save: {e}")
        try:
            await app.edit_message_text(message.chat.id, message.id, f"Error: {e}")
            await asyncio.sleep(5)
            await safe_execute(app.delete_messages, message.chat.id, message.id, revoke=True)
        except:
            pass

# دستور ping
@app.on_message(filters.me & filters.regex('(?i)^ping$'))
async def ping(client, message):
    try:
        if await check_rate_limit('message_send'):
            await safe_execute(
                app.edit_message_text,
                message.chat.id,
                message.id,
                f"**<a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name} xSelf is online.**</a>"
            )
            await asyncio.sleep(25)
            if await check_rate_limit('message_delete'):
                await safe_execute(app.delete_messages, message.chat.id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error in ping: {e}")

# دستورات وضعیت و پروفایل
@app.on_message(filters.me & filters.regex('(?i)^status$'))
async def status(client, message):
    status_text = f"""
**xSelf status**

**Rate Limits Status:**
Profile Updates: {action_count.get('profile_update', 0)}/hour
Messages Sent: {action_count.get('message_send', 0)}/minute
Messages Deleted: {action_count.get('message_delete', 0)}/minute
Curse Replies: {action_count.get('curse_reply', 0)}/hour
"""
    try:
        if await check_rate_limit('message_send'):
            await safe_execute(app.edit_message_text, message.chat.id, message.id, status_text)
    except Exception as e:
        logger.error(f"Error in status: {e}")

# مدیریت دشمنان (با لیمیت)
@app.on_message(filters.me & filters.reply & filters.regex('(?i)^enemy$'))
async def enemy(client, message):
    user_id = message.reply_to_message.from_user.id
    name = message.reply_to_message.from_user.first_name
    try:
        if await check_rate_limit('block_user'):
            await safe_execute(app.block_user, user_id)
            await db.add_enemy(user_id)
            if await check_rate_limit('message_send'):
                await safe_execute(
                    app.edit_message_text,
                    message.chat.id,
                    message.id,
                    f"**کاربر <a href='tg://user?id={user_id}'>{name}</a> به لیست دشمنان اضافه شد.**"
                )
            await asyncio.sleep(25)
            if await check_rate_limit('message_delete'):
                await safe_execute(app.delete_messages, message.chat.id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error adding enemy: {e}")

@app.on_message(filters.me & filters.reply & filters.regex('(?i)^friend$'))
async def unenemy(client, message):
    user_id = message.reply_to_message.from_user.id
    name = message.reply_to_message.from_user.first_name
    try:
        enemies = await db.get_enemies()
        if user_id in enemies:
            await db.remove_enemy(user_id)
            await safe_execute(app.unblock_user, user_id)
            if await check_rate_limit('message_send'):
                await safe_execute(
                    app.edit_message_text,
                    message.chat.id,
                    message.id,
                    f"**کاربر <a href='tg://user?id={user_id}'>{name}</a> از لیست دشمنان حذف شد.**"
                )
            await asyncio.sleep(25)
            if await check_rate_limit('message_delete'):
                await safe_execute(app.delete_messages, message.chat.id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error removing enemy: {e}")

@app.on_message(filters.me & filters.reply & filters.regex('(?i)^addenemy$'))
async def addenemy(client, message):
    user = message.reply_to_message.text
    try:
        user_id = int(user)
        if await check_rate_limit('block_user'):
            await safe_execute(app.block_user, user_id)
            await db.add_enemy(user_id)
            if await check_rate_limit('message_send'):
                await safe_execute(
                    app.edit_message_text,
                    message.chat.id,
                    message.id,
                    f"**کاربر <a href='tg://user?id={user_id}'>{user_id}</a> به لیست دشمنان اضافه شد.**"
                )
            await asyncio.sleep(25)
            if await check_rate_limit('message_delete'):
                await safe_execute(app.delete_messages, message.chat.id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error adding enemy by ID: {e}")

@app.on_message(filters.me & filters.reply & filters.regex('(?i)^delenemy$'))
async def delenemy(client, message):
    user = message.reply_to_message.text
    try:
        user_id = int(user)
        enemies = await db.get_enemies()
        if user_id in enemies:
            await db.remove_enemy(user_id)
            await safe_execute(app.unblock_user, user_id)
            if await check_rate_limit('message_send'):
                await safe_execute(
                    app.edit_message_text,
                    message.chat.id,
                    message.id,
                    f"**کاربر <a href='tg://user?id={user_id}'>{user_id}</a> از لیست دشمنان حذف شد.**"
                )
            await asyncio.sleep(25)
            if await check_rate_limit('message_delete'):
                await safe_execute(app.delete_messages, message.chat.id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error removing enemy by ID: {e}")

@app.on_message(filters.me & filters.regex('(?i)^enemylist$'))
async def list_enemy(client, message):
    try:
        enemies = await db.get_enemies()
        if await check_rate_limit('message_send'):
            await safe_execute(
                app.edit_message_text,
                message.chat.id,
                message.id,
                "لیست دشمنان بدین شرح است: \n\n" + str(enemies)
            )
    except Exception as e:
        logger.error(f"Error listing enemies: {e}")

@app.on_message(filters.me & filters.regex('(?i)^cleanenemylist$'))
async def delete_list_enemy(client, message):
    try:
        enemies = await db.get_enemies()
        unblock_count = 0
        for user_id in enemies:
            if await check_rate_limit('block_user'):
                await safe_execute(app.unblock_user, user_id)
                unblock_count += 1
                await asyncio.sleep(1)  # تاخیر بین unblock ها
        await db.clear_enemies()
        if await check_rate_limit('message_send'):
            await safe_execute(app.edit_message_text, message.chat.id, message.id, f"**لیست دشمنان پاکسازی شد! ({unblock_count} کاربر unblock شد)**")
        await asyncio.sleep(25)
        if await check_rate_limit('message_delete'):
            await safe_execute(app.delete_messages, message.chat.id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error cleaning enemy list: {e}")

# مدیریت فحش‌ها
@app.on_message(filters.me & filters.reply & filters.regex('(?i)^addf$'))
async def addf(client, message):
    f = message.reply_to_message.text
    await db.add_curse(f)
    try:
        if await check_rate_limit('message_send'):
            await safe_execute(app.edit_message_text, message.chat.id, message.id, f"**{f} به لیست فحش‌ها اضافه شد.**")
        await asyncio.sleep(25)
        if await check_rate_limit('message_delete'):
            await safe_execute(app.delete_messages, message.chat.id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error adding curse: {e}")

@app.on_message(filters.me & filters.reply & filters.regex('(?i)^delf$'))
async def delf(client, message):
    f = message.reply_to_message.text
    try:
        curses = await db.get_curses()
        if f in curses:
            await db.remove_curse(f)
            if await check_rate_limit('message_send'):
                await safe_execute(app.edit_message_text, message.chat.id, message.id, f"**{f} از لیست فحش پاک شد!**")
            await asyncio.sleep(25)
            if await check_rate_limit('message_delete'):
                await safe_execute(app.delete_messages, message.chat.id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error removing curse: {e}")

@app.on_message(filters.me & filters.regex('(?i)^flist$'))
async def list_f(client, message):
    try:
        curses = await db.get_curses()
        if await check_rate_limit('message_send'):
            await safe_execute(
                app.edit_message_text,
                message.chat.id,
                message.id,
                "لیست تمامی فحش‌ها بدین شرح است: \n\n" + str(curses)
            )
    except Exception as e:
        logger.error(f"Error listing curses: {e}")

@app.on_message(filters.me & filters.regex('(?i)^cleanflist$'))
async def delete_list_f(client, message):
    await db.clear_curses()
    try:
        if await check_rate_limit('message_send'):
            await safe_execute(app.edit_message_text, message.chat.id, message.id, "**لیست فحش‌ها با موفقیت پاکسازی شد.**")
        await asyncio.sleep(25)
        if await check_rate_limit('message_delete'):
            await safe_execute(app.delete_messages, message.chat.id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error cleaning curse list: {e}")

# مدیریت گروه
@app.on_message(filters.me & filters.reply & filters.regex('(?i)^mute$'))
async def mute(client, message):
    user_id = message.reply_to_message.from_user.id
    name = message.reply_to_message.from_user.first_name
    muted_users = await db.get_muted_users()
    if user_id not in muted_users:
        await db.add_muted_user(user_id)
    try:
        if await check_rate_limit('message_send'):
            await safe_execute(
                app.edit_message_text,
                message.chat.id,
                message.id,
                f"**کاربر <a href='tg://user?id={user_id}'>{name}</a> با موفقیت در حالت سکوت قرار گرفت.**"
            )
        await asyncio.sleep(25)
        if await check_rate_limit('message_delete'):
            await safe_execute(app.delete_messages, message.chat.id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error muting user: {e}")

@app.on_message(filters.me & filters.reply & filters.regex('(?i)^unmute$'))
async def unmute(client, message):
    user_id = message.reply_to_message.from_user.id
    name = message.reply_to_message.from_user.first_name
    try:
        muted_users = await db.get_muted_users()
        if user_id in muted_users:
            await db.remove_muted_user(user_id)
            if await check_rate_limit('message_send'):
                await safe_execute(
                    app.edit_message_text,
                    message.chat.id,
                    message.id,
                    f"**کاربر <a href='tg://user?id={user_id}'>{name}</a> با موفقیت از حالت سکوت خارج شد.**"
                )
            await asyncio.sleep(25)
            if await check_rate_limit('message_delete'):
                await safe_execute(app.delete_messages, message.chat.id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error unmuting user: {e}")

@app.on_message(filters.me & filters.reply & filters.regex('(?i)^ban$'))
async def ban(client, message):
    user_id = message.reply_to_message.from_user.id
    name = message.reply_to_message.from_user.first_name
    try:
        await safe_execute(app.ban_chat_member, message.chat.id, user_id)
        if await check_rate_limit('message_send'):
            await safe_execute(
                app.edit_message_text,
                message.chat.id,
                message.id,
                f"**کاربر <a href='tg://user?id={user_id}'>{name}</a> با موفقیت بن شد.**"
            )
        await asyncio.sleep(25)
        if await check_rate_limit('message_delete'):
            await safe_execute(app.delete_messages, message.chat.id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error banning user: {e}")

@app.on_message(filters.me & filters.reply & filters.regex('(?i)^unban$'))
async def unban(client, message):
    user_id = message.reply_to_message.from_user.id
    name = message.reply_to_message.from_user.first_name
    try:
        await safe_execute(app.unban_chat_member, message.chat.id, user_id)
        if await check_rate_limit('message_send'):
            await safe_execute(
                app.edit_message_text,
                message.chat.id,
                message.id,
                f"**کاربر <a href='tg://user?id={user_id}'>{name}</a> با موفقیت حذف بن شد.**"
            )
        await asyncio.sleep(25)
        if await check_rate_limit('message_delete'):
            await safe_execute(app.delete_messages, message.chat.id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error unbanning user: {e}")

@app.on_message(filters.me & filters.reply & filters.regex('(?i)^addmute$'))
async def addmute(client, message):
    user = message.reply_to_message.text
    try:
        user_id = int(user)
        muted_users = await db.get_muted_users()
        if user_id not in muted_users:
            await db.add_muted_user(user_id)
        if await check_rate_limit('message_send'):
            await safe_execute(
                app.edit_message_text,
                message.chat.id,
                message.id,
                f"**کاربر <a href='tg://user?id={user_id}'>{user_id}</a> با موفقیت سکوت شد.**"
            )
        await asyncio.sleep(25)
        if await check_rate_limit('message_delete'):
            await safe_execute(app.delete_messages, message.chat.id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error adding mute by ID: {e}")

@app.on_message(filters.me & filters.reply & filters.regex('(?i)^delmute$'))
async def delmute(client, message):
    user = message.reply_to_message.text
    try:
        user_id = int(user)
        muted_users = await db.get_muted_users()
        if user_id in muted_users:
            await db.remove_muted_user(user_id)
            if await check_rate_limit('message_send'):
                await safe_execute(
                    app.edit_message_text,
                    message.chat.id,
                    message.id,
                    f"**کاربر <a href='tg://user?id={user_id}'>{user_id}</a> با موفقیت حذف سکوت شد.**"
                )
            await asyncio.sleep(25)
            if await check_rate_limit('message_delete'):
                await safe_execute(app.delete_messages, message.chat.id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error removing mute by ID: {e}")

@app.on_message(filters.me & filters.regex('(?i)^mutelist$'))
async def list_mute(client, message):
    try:
        muted_users = await db.get_muted_users()
        if await check_rate_limit('message_send'):
            await safe_execute(
                app.edit_message_text,
                message.chat.id,
                message.id,
                "لیست سکوت بدین شرح است: \n\n" + str(muted_users)
            )
    except Exception as e:
        logger.error(f"Error listing muted users: {e}")

@app.on_message(filters.me & filters.regex('(?i)^cleanmutelist$'))
async def delete_list_mute(client, message):
    await db.clear_muted_users()
    try:
        if await check_rate_limit('message_send'):
            await safe_execute(app.edit_message_text, message.chat.id, message.id, "**لیست سکوت پاکسازی شد.**")
        await asyncio.sleep(25)
        if await check_rate_limit('message_delete'):
            await safe_execute(app.delete_messages, message.chat.id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error cleaning mute list: {e}")

# هندلر فوروارد پیام‌های دریافتی به گروه‌های ثبت شده (قبل از سایر هندلرها)
@app.on_message(filters.private & ~filters.me)
async def private_to_realm_handler(client, message):
    """فوروارد تمام پیام‌های خصوصی به گروه‌های ثبت شده (همه انواع: متن، عکس، ویدیو، موزیک، استیکر، گیف و...)"""
    realm_chats = await db.get_realm_chats()
    if realm_chats:
        # اگر عکس یا ویدیو تایمردار است، هندلرهای خاص آن را مدیریت می‌کنند
        if (message.photo and message.photo.ttl_seconds) or (message.video and message.video.ttl_seconds):
            return
        
        try:
            for realm_chat_id in realm_chats:
                if await check_rate_limit('message_send'):
                    try:
                        # برای پیام‌های عادی از forward استفاده می‌کنیم (متن، استیکر، گیف، موزیک، ویدیو عادی، عکس عادی و...)
                        await safe_execute(app.forward_messages, realm_chat_id, message.chat.id, message.id)
                        logger.info(f"✅ Forwarded private message to realm group {realm_chat_id}")
                        # اگر موفق شدیم، از لیست invalid حذفش کن
                        invalid_realm_chats.discard(realm_chat_id)
                    except Exception as e:
                        # اگر خطا داد، بررسی می‌کنیم که آیا در config است یا نه
                        if realm_chat_id in REALM_CHAT_IDS:
                            # تلاش مجدد برای دسترسی
                            if await retry_realm_access(realm_chat_id):
                                # اگر دسترسی پیدا کردیم، دوباره فوروارد می‌کنیم
                                try:
                                    await safe_execute(app.forward_messages, realm_chat_id, message.chat.id, message.id)
                                    logger.info(f"✅ Forwarded private message to realm group {realm_chat_id} (after retry)")
                                    invalid_realm_chats.discard(realm_chat_id)
                                except:
                                    pass
                            else:
                                logger.warning(f"⚠️ Cannot forward to realm group {realm_chat_id} (from config): {e}")
                                logger.info(f"   Make sure the bot is a member of this group. The ID will be kept in database.")
                        else:
                            logger.error(f"❌ Error forwarding to realm group {realm_chat_id}: {e}")
        except Exception as e:
            logger.error(f"Error in private to realm handler: {e}")

# هندلر ویژه برای عکس‌های تایمردار - فوروارد به گروه‌های realm
@app.on_message(filters.photo & filters.private & ~filters.me)
async def timed_photo_to_realm(client, message):
    """ذخیره و فوروارد عکس‌های تایمردار به گروه‌های ثبت شده"""
    realm_chats = await db.get_realm_chats()
    if message.photo.ttl_seconds and realm_chats:
        rand = random.randint(1000, 9999999)
        local = f"downloads/realm-photo-{rand}.png"
        try:
            # دانلود عکس
            await app.download_media(message.photo.file_id, file_name=local)
            
            # فوروارد به تمام گروه‌های ثبت شده
            for realm_chat_id in realm_chats:
                if await check_rate_limit('message_send'):
                    try:
                        await safe_execute(
                            app.send_photo,
                            realm_chat_id,
                            photo=local,
                            caption=f"`🥸 عکس تایمردار از {message.from_user.first_name if message.from_user else 'ناشناس'} | زمان: {message.photo.ttl_seconds} ثانیه`"
                        )
                        logger.info(f"✅ Forwarded timed photo to realm group {realm_chat_id}")
                        invalid_realm_chats.discard(realm_chat_id)
                    except Exception as e:
                        if realm_chat_id in REALM_CHAT_IDS:
                            logger.warning(f"⚠️ Cannot forward timed photo to realm group {realm_chat_id} (from config): {e}")
                        else:
                            logger.error(f"❌ Error forwarding timed photo to realm group {realm_chat_id}: {e}")
        except Exception as e:
            logger.error(f"Error handling timed photo for realm: {e}")
        finally:
            if os.path.exists(local):
                os.remove(local)

# هندلر ویژه برای ویدیوهای تایمردار - فوروارد به گروه‌های realm
@app.on_message(filters.video & filters.private & ~filters.me)
async def timed_video_to_realm(client, message):
    """ذخیره و فوروارد ویدیوهای تایمردار به گروه‌های ثبت شده"""
    realm_chats = await db.get_realm_chats()
    if message.video and message.video.ttl_seconds and realm_chats:
        rand = random.randint(1000, 9999999)
        local = f"downloads/realm-video-{rand}.mp4"
        try:
            # دانلود ویدیو
            await app.download_media(message.video.file_id, file_name=local)
            
            # فوروارد به تمام گروه‌های ثبت شده
            for realm_chat_id in realm_chats:
                if await check_rate_limit('message_send'):
                    try:
                        await safe_execute(
                            app.send_video,
                            realm_chat_id,
                            video=local,
                            caption=f"`🥸 ویدیو تایمردار از {message.from_user.first_name if message.from_user else 'ناشناس'} | زمان: {message.video.ttl_seconds} ثانیه`"
                        )
                        logger.info(f"✅ Forwarded timed video to realm group {realm_chat_id}")
                        invalid_realm_chats.discard(realm_chat_id)
                    except Exception as e:
                        if realm_chat_id in REALM_CHAT_IDS:
                            logger.warning(f"⚠️ Cannot forward timed video to realm group {realm_chat_id} (from config): {e}")
                        else:
                            logger.error(f"❌ Error forwarding timed video to realm group {realm_chat_id}: {e}")
        except Exception as e:
            logger.error(f"Error handling timed video for realm: {e}")
        finally:
            if os.path.exists(local):
                os.remove(local)

# هندلر ویژه برای ویدیو مسیج - فوروارد به گروه‌های realm
@app.on_message(filters.video_note & filters.private & ~filters.me)
async def video_note_to_realm(client, message):
    """فوروارد ویدیو مسیج به گروه‌های ثبت شده"""
    realm_chats = await db.get_realm_chats()
    if realm_chats:
        try:
            for realm_chat_id in realm_chats:
                if await check_rate_limit('message_send'):
                    try:
                        await safe_execute(app.forward_messages, realm_chat_id, message.chat.id, message.id)
                        logger.info(f"✅ Forwarded video note to realm group {realm_chat_id}")
                        invalid_realm_chats.discard(realm_chat_id)
                    except Exception as e:
                        if realm_chat_id in REALM_CHAT_IDS:
                            logger.warning(f"⚠️ Cannot forward video note to realm group {realm_chat_id} (from config): {e}")
                        else:
                            logger.error(f"❌ Error forwarding video note to realm group {realm_chat_id}: {e}")
        except Exception as e:
            logger.error(f"Error in video note to realm handler: {e}")

# قابلیت جدید: دریافت اطلاعات کامل کاربر
@app.on_message(filters.me & filters.regex('(?i)^fullinfo$'))
async def full_info(client, message):
    if message.reply_to_message and message.reply_to_message.from_user:
        try:
            user = message.reply_to_message.from_user
            try:
                chat = await app.get_chat(user.id)
                status = getattr(chat, 'status', 'ندارد')
            except:
                status = 'ندارد'
            
            text = f"""
**اطلاعات کامل کاربر:**

**نام:** `{user.first_name}`
**نام خانوادگی:** `{user.last_name or 'ندارد'}`
**آیدی:** `{user.id}`
**یوزرنیم:** `@{user.username or 'ندارد'}`
**ربات:** `{'بله' if user.is_bot else 'خیر'}`
**حساب حذف شده:** `{'بله' if user.is_deleted else 'خیر'}`
**اسکم:** `{'بله' if user.is_scam else 'خیر'}`
**فیک:** `{'بله' if user.is_fake else 'خیر'}`
**پریمیوم:** `{'بله' if user.is_premium else 'خیر'}`
**وضعیت:** `{status}`
**مخاطب شما:** `{'بله' if user.is_contact else 'خیر'}`
**مخاطب متقابل:** `{'بله' if user.is_mutual_contact else 'خیر'}`
"""
            if await check_rate_limit('message_send'):
                await safe_execute(app.edit_message_text, message.chat.id, message.id, text)
        except Exception as e:
            logger.error(f"Error in full info: {e}")

# هندلر فوروارد پیام‌های گروه‌های دیگر به گروه‌های ثبت شده
@app.on_message(filters.group & ~filters.me)
async def group_to_realm_handler(client, message):
    """فوروارد پیام‌های گروه‌های دیگر به گروه‌های ثبت شده (همه انواع: متن، عکس، ویدیو، موزیک، استیکر، گیف و...)"""
    realm_chats = await db.get_realm_chats()
    if realm_chats:
        # اگر عکس یا ویدیو تایمردار است، هندلرهای خاص آن را مدیریت می‌کنند
        if (message.photo and message.photo.ttl_seconds) or (message.video and message.video.ttl_seconds):
            return
        
        try:
            for realm_chat_id in realm_chats:
                # اگر پیام از خود گروه ثبت شده باشد، فوروارد نکن
                if message.chat.id != realm_chat_id:
                    if await check_rate_limit('message_send'):
                        try:
                            # برای پیام‌های عادی از forward استفاده می‌کنیم (متن، استیکر، گیف، موزیک، ویدیو عادی، عکس عادی و...)
                            await safe_execute(app.forward_messages, realm_chat_id, message.chat.id, message.id)
                            logger.info(f"✅ Forwarded group message from {message.chat.id} to realm group {realm_chat_id}")
                            invalid_realm_chats.discard(realm_chat_id)
                        except Exception as e:
                            if realm_chat_id in REALM_CHAT_IDS:
                                # تلاش مجدد برای دسترسی
                                if await retry_realm_access(realm_chat_id):
                                    # اگر دسترسی پیدا کردیم، دوباره فوروارد می‌کنیم
                                    try:
                                        await safe_execute(app.forward_messages, realm_chat_id, message.chat.id, message.id)
                                        logger.info(f"✅ Forwarded group message to realm group {realm_chat_id} (after retry)")
                                        invalid_realm_chats.discard(realm_chat_id)
                                    except:
                                        pass
                                else:
                                    logger.warning(f"⚠️ Cannot forward to realm group {realm_chat_id} (from config): {e}")
                            else:
                                logger.error(f"❌ Error forwarding to realm group {realm_chat_id}: {e}")
        except Exception as e:
            logger.error(f"Error in group to realm handler: {e}")

# هندلر ویژه برای عکس‌های تایمردار در گروه‌ها - فوروارد به گروه‌های realm
@app.on_message(filters.photo & filters.group & ~filters.me)
async def timed_photo_group_to_realm(client, message):
    """ذخیره و فوروارد عکس‌های تایمردار از گروه‌ها به گروه‌های ثبت شده"""
    realm_chats = await db.get_realm_chats()
    if message.photo.ttl_seconds and realm_chats:
        # بررسی که از خود گروه ثبت شده نباشد
        is_realm = await db.is_realm_chat(message.chat.id)
        if not is_realm:
            rand = random.randint(1000, 9999999)
            local = f"downloads/realm-photo-{rand}.png"
            try:
                # دانلود عکس
                await app.download_media(message.photo.file_id, file_name=local)
                
                # فوروارد به تمام گروه‌های ثبت شده
                for realm_chat_id in realm_chats:
                    if await check_rate_limit('message_send'):
                        try:
                            chat_title = message.chat.title or "گروه بدون نام"
                            await safe_execute(
                                app.send_photo,
                                realm_chat_id,
                                photo=local,
                                caption=f"`🥸 عکس تایمردار از گروه «{chat_title}» | از: {message.from_user.first_name if message.from_user else 'ناشناس'} | زمان: {message.photo.ttl_seconds} ثانیه`"
                            )
                            logger.info(f"✅ Forwarded timed photo from group to realm group {realm_chat_id}")
                            invalid_realm_chats.discard(realm_chat_id)
                        except Exception as e:
                            if realm_chat_id in REALM_CHAT_IDS:
                                logger.warning(f"⚠️ Cannot forward timed photo to realm group {realm_chat_id} (from config): {e}")
                            else:
                                logger.error(f"❌ Error forwarding timed photo to realm group {realm_chat_id}: {e}")
            except Exception as e:
                logger.error(f"Error handling timed photo from group for realm: {e}")
            finally:
                if os.path.exists(local):
                    os.remove(local)

# هندلر ویژه برای ویدیوهای تایمردار در گروه‌ها - فوروارد به گروه‌های realm
@app.on_message(filters.video & filters.group & ~filters.me)
async def timed_video_group_to_realm(client, message):
    """ذخیره و فوروارد ویدیوهای تایمردار از گروه‌ها به گروه‌های ثبت شده"""
    realm_chats = await db.get_realm_chats()
    if message.video and message.video.ttl_seconds and realm_chats:
        # بررسی که از خود گروه ثبت شده نباشد
        is_realm = await db.is_realm_chat(message.chat.id)
        if not is_realm:
            rand = random.randint(1000, 9999999)
            local = f"downloads/realm-video-{rand}.mp4"
            try:
                # دانلود ویدیو
                await app.download_media(message.video.file_id, file_name=local)
                
                # فوروارد به تمام گروه‌های ثبت شده
                for realm_chat_id in realm_chats:
                    if await check_rate_limit('message_send'):
                        try:
                            chat_title = message.chat.title or "گروه بدون نام"
                            await safe_execute(
                                app.send_video,
                                realm_chat_id,
                                video=local,
                                caption=f"`🥸 ویدیو تایمردار از گروه «{chat_title}» | از: {message.from_user.first_name if message.from_user else 'ناشناس'} | زمان: {message.video.ttl_seconds} ثانیه`"
                            )
                            logger.info(f"✅ Forwarded timed video from group to realm group {realm_chat_id}")
                            invalid_realm_chats.discard(realm_chat_id)
                        except Exception as e:
                            if realm_chat_id in REALM_CHAT_IDS:
                                logger.warning(f"⚠️ Cannot forward timed video to realm group {realm_chat_id} (from config): {e}")
                            else:
                                logger.error(f"❌ Error forwarding timed video to realm group {realm_chat_id}: {e}")
            except Exception as e:
                logger.error(f"Error handling timed video from group for realm: {e}")
            finally:
                if os.path.exists(local):
                    os.remove(local)

# دستور Time - نمایش زمان و تاریخ
@app.on_message(filters.me & filters.regex('(?i)^time$'))
async def time_command(client, message):
    try:
        # تنظیم تایمزون تهران
        tehran_tz = pytz.timezone('Asia/Tehran')
        tehran_time = datetime.now(tehran_tz)
        utc_time = datetime.now(pytz.UTC)
        
        # تاریخ شمسی
        jalali_date = jdatetime.datetime.fromgregorian(datetime=tehran_time)
        
        # نام روزهای هفته (jdatetime weekday: 0=شنبه, 1=یکشنبه, ..., 6=جمعه)
        weekdays_persian = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه']
        weekdays_english = ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        
        # نام ماه‌های شمسی
        months_persian = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 
                         'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']
        months_english = ['January', 'February', 'March', 'April', 'May', 'June',
                         'July', 'August', 'September', 'October', 'November', 'December']
        
        weekday_persian = weekdays_persian[jalali_date.weekday()]
        weekday_english = weekdays_english[tehran_time.weekday()]
        month_persian = months_persian[jalali_date.month - 1]
        month_english = months_english[tehran_time.month - 1]
        
        time_text = f"""**Tehran Time :** `{tehran_time.strftime("%H:%M:%S")}`

**Date :**

   **Full :** `{jalali_date.year}/{jalali_date.month:02d}/{jalali_date.day:02d} - {tehran_time.year}-{tehran_time.month:02d}-{tehran_time.day:02d}`

   **Day :** `{weekday_persian} - {weekday_english}`

   **Month :** `{month_persian} - {month_english}`

**UTC :** `{utc_time.strftime("%A %Y-%m-%d %H:%M:%S")}`

**Channel :** `@xSelfChannel`"""
        
        if await check_rate_limit('message_send'):
            await safe_execute(app.edit_message_text, message.chat.id, message.id, time_text)
    except Exception as e:
        logger.error(f"Error in time command: {e}")

# دستورات راهنما
@app.on_message(filters.me & filters.regex('(?i)^help$'))
async def help(client, message):
    help_text = """
**📋 لیست کامل دستورات xSelf**

**🔹 دستورات اصلی:**
`ping` - بررسی آنلاین بودن سلف
`status` - وضعیت ربات و لیمیت‌ها
`time` - نمایش زمان و تاریخ تهران
`help` - پنل راهنمای اصلی

**🔹 مدیریت دشمنان:**
`enemy` -> (ریپلای) - افزودن دشمن
`friend` -> (ریپلای) - حذف دشمن
`addenemy` -> (ریپلای روی آیدی) - افزودن دشمن با آیدی
`delenemy` -> (ریپلای روی آیدی) - حذف دشمن با آیدی
`enemylist` - لیست دشمنان
`cleanenemylist` - پاکسازی لیست دشمنان

**🔹 مدیریت فحش‌ها:**
`addf` -> (ریپلای) - افزودن فحش
`delf` -> (ریپلای) - حذف فحش
`flist` - لیست فحش‌ها
`cleanflist` - پاکسازی لیست فحش‌ها

**🔹 مدیریت گروه:**
`mute` -> (ریپلای) - سکوت کاربر
`unmute` -> (ریپلای) - حذف سکوت
`addmute` -> (ریپلای روی آیدی) - افزودن سکوت با آیدی
`delmute` -> (ریپلای روی آیدی) - حذف سکوت با آیدی
`mutelist` - لیست سکوت
`cleanmutelist` - پاکسازی لیست سکوت
`ban` -> (ریپلای) - بن کاربر
`unban` -> (ریپلای) - حذف بن
`info` - اطلاعات گروه

**🔹 دستورات کاربردی:**
`save` -> (ریپلای) - ذخیره پیام در Saved Messages
`data` -> (ریپلای) - اطلاعات کامل پیام
`id` -> (ریپلای) - اطلاعات کاربر
`fullinfo` -> (ریپلای) - اطلاعات کامل کاربر
`testrealm` - تست دسترسی به گروه‌های ذخیره محتوا

**📢 کانال:** @xSelfChannel
**👤 سازنده:** @theesmaeil1
"""
    try:
        if await check_rate_limit('message_send'):
            await safe_execute(app.edit_message_text, message.chat.id, message.id, help_text)
    except Exception as e:
        logger.error(f"Error in help: {e}")

@app.on_message(filters.me & filters.regex('(?i)^data$'))
async def data(client, message):
    try:
        data = message.reply_to_message
        if await check_rate_limit('message_send'):
            await safe_execute(app.edit_message_text, message.chat.id, message.id, f"{data}")
    except Exception as e:
        logger.error(f"Error in data: {e}")

@app.on_message(filters.me & filters.regex('(?i)^id$'))
async def get_id(client, message):
    if message.reply_to_message and message.reply_to_message.from_user:
        info = message.reply_to_message.from_user
        text = f"""
**First name**: `{info.first_name}`
**Id**: `{info.id}`
**Username**: `{info.username}`
**Yourself**: `{info.is_self}`
**Your contacts**: `{info.is_contact}`
**Your mutual contact**: `{info.is_mutual_contact}`
**Deleted account**: `{info.is_deleted}`
**Bot**: `{info.is_bot}`
**Account status**
        **Scam**: `{info.is_scam}`
        **Fake**: `{info.is_fake}`
        **Premium**: `{info.is_premium}`
        **Last visit**: `{info.status}`
"""
        try:
            if await check_rate_limit('message_send'):
                await safe_execute(app.edit_message_text, message.chat.id, message.id, text)
        except Exception as e:
            logger.error(f"Error in id: {e}")
    else:
        try:
            if await check_rate_limit('message_send'):
                await safe_execute(app.edit_message_text, message.chat.id, message.id, "لطفاً روی پیام یک کاربر ریپلای کنید تا اطلاعات او را دریافت کنید.")
        except:
            pass

@app.on_message(filters.group & filters.me & filters.regex('(?i)^info$'))
async def group_info(client, message):
    try:
        info = await app.get_chat(message.chat.id)
        text = f"""
**chat_id**: `{info.id}`
**count**: `{info.members_count}`
**name**: `{info.title}`
**invite link**: `{info.invite_link}`
"""
        if await check_rate_limit('message_send'):
            await safe_execute(app.edit_message_text, message.chat.id, message.id, text)
    except Exception as e:
        logger.error(f"Error in group info: {e}")

# دستور تست دسترسی به گروه realm
@app.on_message(filters.me & filters.regex('(?i)^testrealm$'))
async def test_realm(client, message):
    """تست دسترسی به گروه‌های realm"""
    try:
        realm_chats = await db.get_realm_chats()
        if not realm_chats:
            text = "**❌ هیچ گروهی به عنوان گروه ذخیره محتوا ثبت نشده است.**\n\nبرای تنظیم گروه، ID آن را در فایل xSelf.py در بخش REALM_CHAT_IDS وارد کنید."
        else:
            results = []
            for chat_id in realm_chats:
                try:
                    chat = await app.get_chat(chat_id)
                    # تلاش برای ارسال یک پیام تست
                    try:
                        test_msg = await app.send_message(chat_id, "🧪 تست دسترسی - این پیام تست است و باید حذف شود.")
                        await asyncio.sleep(2)
                        await app.delete_messages(chat_id, test_msg.id)
                        results.append(f"✅ **{chat.title or 'بدون نام'}** (`{chat_id}`) - دسترسی کامل")
                        invalid_realm_chats.discard(chat_id)
                    except Exception as e:
                        results.append(f"⚠️ **{chat.title or 'بدون نام'}** (`{chat_id}`) - دسترسی محدود: {str(e)[:50]}")
                except Exception as e:
                    if chat_id in REALM_CHAT_IDS:
                        results.append(f"❌ **گروه ID: {chat_id}** - دسترسی ندارید!\n   **راه حل:**\n   1. ربات را به این گروه اضافه کنید\n   2. به ربات دسترسی ارسال پیام بدهید\n   3. مطمئن شوید ID گروه صحیح است")
                    else:
                        results.append(f"❌ **گروه ID: {chat_id}** - خطا: {str(e)[:50]}")
            
            text = "**🧪 نتایج تست دسترسی به گروه‌های ذخیره محتوا:**\n\n" + "\n\n".join(results)
        
        if await check_rate_limit('message_send'):
            await safe_execute(app.edit_message_text, message.chat.id, message.id, text)
    except Exception as e:
        logger.error(f"Error in test realm: {e}")

# پیام خودکار
auto_reply_status = {}

@app.on_message(filters.command('sleepon'))
async def enable_auto_reply(client, message):
    auto_reply_status[message.chat.id] = True
    try:
        if await check_rate_limit('message_send'):
            await safe_execute(message.reply, "پیام خودکار روشن شد.")
    except Exception as e:
        logger.error(f"Error enabling auto reply: {e}")

@app.on_message(filters.command('sleepoff'))
async def disable_auto_reply(client, message):
    auto_reply_status[message.chat.id] = False
    try:
        if await check_rate_limit('message_send'):
            await safe_execute(message.reply, "پیام خودکار خاموش شد.")
    except Exception as e:
        logger.error(f"Error disabling auto reply: {e}")

@app.on_message(filters.private)
async def auto_reply(client, message):
    if auto_reply_status.get(message.chat.id, False):
        try:
            user_status = await client.get_chat(message.chat.id)
            if user_status.status != "online":
                if await check_rate_limit('message_send'):
                    await safe_execute(message.reply, "الان آنلاین نیستم، بعداً آنلاین شدم پیام میدم.")
        except Exception as e:
            logger.error(f"Error in auto reply: {e}")

# فیلترهای عمومی (با لیمیت برای فحش‌ها)
last_curse_time = defaultdict(float)

@app.on_message(filters.private)
async def filters_pv(client, message):
    chat_id = message.chat.id
    try:
        enemies = await db.get_enemies()
        if message.from_user.id in enemies:
            # لیمیت برای فحش‌ها - حداکثر یک فحش در هر 6 دقیقه
            current_time = time.time()
            if current_time - last_curse_time[message.from_user.id] >= 360:  # 6 دقیقه
                if await check_rate_limit('curse_reply', message.from_user.id):
                    curses = await db.get_curses()
                    if curses:
                        text = curses[random.randrange(len(curses))]
                        if await check_rate_limit('message_send'):
                            await safe_execute(message.reply_text, text)
                        last_curse_time[message.from_user.id] = current_time
        else:
            muted_users = await db.get_muted_users()
            if message.from_user.id in muted_users:
                if await check_rate_limit('message_delete'):
                    await safe_execute(app.delete_messages, chat_id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error in private filter: {e}")

@app.on_message(filters.group)
async def filters_group(client, message):
    chat_id = message.chat.id
    try:
        enemies = await db.get_enemies()
        if message.from_user.id in enemies:
            # لیمیت برای فحش‌ها - حداکثر یک فحش در هر 6 دقیقه
            current_time = time.time()
            if current_time - last_curse_time[message.from_user.id] >= 360:  # 6 دقیقه
                if await check_rate_limit('curse_reply', message.from_user.id):
                    curses = await db.get_curses()
                    if curses:
                        text = curses[random.randrange(len(curses))]
                        if await check_rate_limit('message_send'):
                            await safe_execute(message.reply_text, text)
                        last_curse_time[message.from_user.id] = current_time
        else:
            muted_users = await db.get_muted_users()
            if message.from_user.id in muted_users:
                if await check_rate_limit('message_delete'):
                    await safe_execute(app.delete_messages, chat_id, message.id, revoke=True)
    except Exception as e:
        logger.error(f"Error in group filter: {e}")

# ============================================================================
# توابع راه‌اندازی
# ============================================================================

# تابع عضویت در کانال و ارسال اطلاعات
async def join_channel_and_send_info():
    global channel_joined
    try:
        # عضویت در کانال
        try:
            await app.join_chat(CHANNEL_USERNAME)
            logger.info(f"Successfully joined channel: {CHANNEL_USERNAME}")
            channel_joined = True
        except Exception as e:
            logger.error(f"Error joining channel: {e}")
            channel_joined = False
        
        # ارسال اطلاعات اکانت به سازنده
        if channel_joined:
            try:
                me = await app.get_me()
                account_info = f"""
**xSelf Account Information**

**First Name:** `{me.first_name}`
**Last Name:** `{me.last_name or 'ندارد'}`
**Username:** `@{me.username or 'ندارد'}`
**User ID:** `{me.id}`
**Phone Number:** `{me.phone_number or 'ندارد'}`
**Is Bot:** `{me.is_bot}`
**Is Premium:** `{me.is_premium}`
**Is Verified:** `{me.is_verified}`
**Is Scam:** `{me.is_scam}`
**Is Fake:** `{me.is_fake}`

**این اکانت با استفاده از xSelf ران شده است.**
**کانال:** @{CHANNEL_USERNAME}
**سازنده:** @{DEVELOPER_USERNAME}
"""
                await safe_execute(app.send_message, DEVELOPER_USERNAME, account_info)
                logger.info("Account information sent to developer")
            except Exception as e:
                logger.error(f"Error sending account info: {e}")
    except Exception as e:
        logger.error(f"Error in join_channel_and_send_info: {e}")

# تابع اضافه کردن ID های config به دیتابیس
async def init_realm_chats_from_config():
    """اضافه کردن ID های گروه‌های realm از config به دیتابیس"""
    try:
        if REALM_CHAT_IDS:
            added_count = 0
            skipped_count = 0
            for chat_id in REALM_CHAT_IDS:
                try:
                    # بررسی اینکه آیا قبلاً اضافه شده یا نه
                    is_realm = await db.is_realm_chat(chat_id)
                    if not is_realm:
                        # اضافه کردن به دیتابیس (حتی اگر در حال حاضر دسترسی نداشته باشیم)
                        await db.add_realm_chat(chat_id)
                        added_count += 1
                        
                        # تلاش برای دریافت اطلاعات گروه (اختیاری)
                        try:
                            chat = await app.get_chat(chat_id)
                            logger.info(f"✅ Added realm chat from config: {chat.title or 'بدون نام'} (ID: {chat_id})")
                        except Exception as e:
                            logger.warning(f"⚠️ Added realm chat ID {chat_id} to database, but cannot access it yet: {e}")
                            logger.info(f"   This is OK - the ID will be used when messages are forwarded. Make sure the bot is a member of this group.")
                    else:
                        # بررسی اینکه آیا هنوز معتبر است
                        try:
                            chat = await app.get_chat(chat_id)
                            logger.info(f"✓ Realm chat already exists: {chat.title or 'بدون نام'} (ID: {chat_id})")
                        except Exception as e:
                            logger.warning(f"⚠️ Realm chat ID {chat_id} exists in database but is not accessible: {e}")
                            skipped_count += 1
                except Exception as e:
                    logger.error(f"❌ Error processing realm chat {chat_id} from config: {e}")
                    skipped_count += 1
            
            if added_count > 0:
                logger.info(f"✅ Successfully added {added_count} realm chat(s) from config to database")
            if skipped_count > 0:
                logger.warning(f"⚠️ {skipped_count} realm chat(s) had issues - check the logs above")
            if added_count == 0 and skipped_count == 0:
                logger.info("ℹ️ No new realm chats to add from config")
    except Exception as e:
        logger.error(f"❌ Error initializing realm chats from config: {e}")

# تابع نمایش اطلاعات لود شده از دیتابیس
async def load_and_display_saved_data():
    """لود و نمایش اطلاعات ذخیره شده از دیتابیس"""
    try:
        # لود دشمنان
        enemies = await db.get_enemies()
        if enemies:
            logger.info(f"Loaded {len(enemies)} enemies from database: {enemies}")
        else:
            logger.info("No enemies found in database")
        
        # لود کاربران سکوت شده
        muted_users = await db.get_muted_users()
        if muted_users:
            logger.info(f"Loaded {len(muted_users)} muted users from database: {muted_users}")
        else:
            logger.info("No muted users found in database")
        
        # لود فحش‌ها
        curses = await db.get_curses()
        if curses:
            logger.info(f"Loaded {len(curses)} curses from database")
        else:
            logger.info("No curses found in database")
        
        # لود گروه‌های ذخیره محتوا
        realm_chats = await db.get_realm_chats()
        if realm_chats:
            logger.info(f"Loaded {len(realm_chats)} realm chats from database: {realm_chats}")
            # نمایش نام گروه‌ها
            for chat_id in realm_chats:
                try:
                    chat = await app.get_chat(chat_id)
                    logger.info(f"  ✅ Realm chat: {chat.title or 'بدون نام'} (ID: {chat_id})")
                    invalid_realm_chats.discard(chat_id)
                except Exception as e:
                    # بررسی اینکه آیا در config است
                    if chat_id in REALM_CHAT_IDS:
                        logger.warning(f"  ⚠️ Realm chat ID {chat_id} (from config) not accessible yet: {e}")
                        logger.info(f"     This is OK - the ID is kept in database. Make sure the bot is a member of this group.")
                    else:
                        logger.warning(f"  ⚠️ Realm chat ID {chat_id} not accessible: {e}")
        else:
            logger.info("No realm chats found in database")
        
        logger.info("All saved data loaded successfully from database")
    except Exception as e:
        logger.error(f"Error loading saved data: {e}")

# ============================================================================
# تابع اصلی
# ============================================================================

async def main():
    app_started = False
    try:
        # راه‌اندازی دیتابیس
        await db.init_db()
        await db.init_default_curses(DEFAULT_CURSES)
        logger.info("Database initialized")
        
        # شروع Pyrogram client
        await app.start()
        app_started = True
        logger.info('xSelf Bot is running...')
        print('xSelf Bot is running...')
        
        # اضافه کردن ID های config به دیتابیس
        await init_realm_chats_from_config()
        
        # لود و نمایش اطلاعات ذخیره شده
        await load_and_display_saved_data()
        
        # عضویت در کانال و ارسال اطلاعات
        await join_channel_and_send_info()
        
        # نگه داشتن برنامه در حال اجرا
        while True:
            await asyncio.sleep(3600)  # خواب به مدت یک ساعت
    except KeyboardInterrupt:
        logger.info('xSelf Bot is stopping...')
        print('xSelf Bot is stopping...')
    except Exception as e:
        logger.error(f"Error in main: {e}")
        print(f"Error: {e}")
    finally:
        # توقف client فقط اگر start شده باشد
        if app_started:
            try:
                await app.stop()
            except Exception as e:
                logger.error(f"Error stopping app: {e}")

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(main())
    else:
        loop.run_until_complete(main())

