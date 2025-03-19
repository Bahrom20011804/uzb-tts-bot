import os
import re
import pandas as pd
import asyncio
import pysrt
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import FSInputFile
from aiogram.filters import Command
from aiogram.types import Message
from pydub import AudioSegment
from aiogram.client.session.aiohttp import AiohttpSession
import sqlite3
import sys
from dotenv import dotenv_values

config = dotenv_values("u.env")  # `u.env` faylini yuklash
TOKEN = config.get("BOT_TOKEN")



# 🔹 Bot sozlamalari
session = AiohttpSession(timeout=300)
bot = Bot(token=TOKEN, session=session)
dp = Dispatcher()

# 🔹 Fayllar uchun yo‘llar
CSV_PATH = "dataset/metadata.csv"
BASE_PATH = "dataset/"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
DB_FILE = "users.db"
# 🔹 CSV faylni yuklash
def load_audio_mapping():
    if not os.path.exists(CSV_PATH):
        return {}
    df = pd.read_csv(CSV_PATH, names=["audio_path", "syllable"])  # 🔹 "letter" o‘rniga "syllable"
    return {row["syllable"]: os.path.join(BASE_PATH, row["audio_path"]) for _, row in df.iterrows()}

AUDIO_MAPPING = load_audio_mapping()

SPECIAL_CHARS = ["ch", "sh", "o'", "o‘", "g'", "g‘"]

# 🔹 So‘zni maxsus harflarni hisobga olib ajratish
def harflarga_ajrat(soz):
    natija = []
    i = 0
    while i < len(soz):
        if i < len(soz) - 1 and soz[i:i+2] in SPECIAL_CHARS:
            natija.append(soz[i:i+2])
            i += 2
        else:
            natija.append(soz[i])
            i += 1
    return natija

# 🔹 Matndan ovoz yaratish
def generate_text_audio(text):
    harflar = harflarga_ajrat(text)  
    all_audio = AudioSegment.silent(duration=300)

    for harf in harflar:
        if harf in AUDIO_MAPPING:
            harf_audio = AudioSegment.from_file(AUDIO_MAPPING[harf])
            all_audio += harf_audio + AudioSegment.silent(duration=50)
        else:
            print(f"❌ `{harf}` uchun ovoz yo‘q!")

    return all_audio
def split_number_correctly(number):
    num = int(number)
    
    if num in AUDIO_MAPPING:
        return [str(num)]
    
    parts = []
    
    trillion = num // 1_000_000_000_000  # Trillion qismi
    remainder = num % 1_000_000_000_000  

    if trillion:
        parts.extend(split_three_digit(trillion))  
        parts.append("1000000000000")  # 1 trillion
    
    billion = remainder // 1_000_000_000  # Milliard qismi
    remainder = remainder % 1_000_000_000  

    if billion:
        parts.extend(split_three_digit(billion))  
        parts.append("1000000000")  # 1 milliard

    million = remainder // 1_000_000  # Million qismi
    remainder = remainder % 1_000_000  

    if million:
        parts.extend(split_three_digit(million))  
        parts.append("1000000")  # 1 million

    thousand = remainder // 1000  # Minglik qismi
    remainder = remainder % 1000  

    if thousand:
        parts.extend(split_three_digit(thousand))  
        parts.append("1000")  # 1 ming

    if remainder:
        parts.extend(split_three_digit(remainder))  

    return parts

def split_two_digit(num):
    """Ikki xonali sonni (56 → 50, 6) ajratish"""
    if num < 20 or num in AUDIO_MAPPING:
        return [str(num)]
    tens = (num // 10) * 10  # O‘nliklar (masalan, 50)
    ones = num % 10  # Birliklar (masalan, 6)
    return [str(tens), str(ones)] if ones else [str(tens)]

def split_three_digit(num):
    """Uch xonali sonni (485 → 4, 100, 80, 5) ajratish"""
    if num in AUDIO_MAPPING:
        return [str(num)]

    parts = []
    hundreds = num // 100  # Yuzlik (masalan, 4)
    remainder = num % 100  # Qolgan son (masalan, 85)

    if hundreds:
        parts.append(str(hundreds))
        parts.append("100")  # 100 qo‘shish

    if remainder:
        parts.extend(split_two_digit(remainder))  # Masalan, 85 → 80, 5

    return parts



# ✅ **Matndan audio yaratish**
def generate_text_audio(text):
    words = text.split()
    all_audio = AudioSegment.silent(duration=300)

    for word in words:
        syllables = harflarga_ajrat(word)  # 🔹 Bo‘g‘inlarga ajratish
        if syllables is None:
            print(f"❌ Xatolik: `{word}` uchun tokenize() None qaytardi!")
            continue  # 🚀 Xatolik bo‘lsa, davom etamiz

        for syllable in syllables:
            if syllable in AUDIO_MAPPING:
                syllable_audio = AudioSegment.from_file(AUDIO_MAPPING[syllable])
                all_audio += syllable_audio + AudioSegment.silent(duration=50)

    return all_audio

# ✅ **SRT fayldan matn olish**
def read_srt_text(file_path):
    return " ".join([sub.text for sub in pysrt.open(file_path)])

# ✅ **Ovoz faylini saqlash**
def save_audio(audio, filename="output", format="mp3"):
    output_path = f"{filename}.{format}"
    audio.export(output_path, format=format, bitrate="64k")
    return output_path

# ✅ **Start komandasi**
@dp.message(Command("start"))
async def send_welcome(message: Message):
    await message.answer("👋 Salom! So‘z yoki .srt fayl yuboring, men uni ovozga aylantirib beraman.")

# ✅ Bazani yaratish
def setup_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

# ✅ Foydalanuvchini qo‘shish
def add_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

# ✅ Obunachilar sonini ko‘rish
def get_subscriber_count():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count
# ✅ **Matnni ovozga o‘tkazish**
@dp.message(F.text)
async def handle_text(message: Message):
    final_audio = generate_text_audio(message.text)
    if final_audio:
        output_file = save_audio(final_audio)
        await message.answer_voice(FSInputFile(output_file))
    else:
        await message.answer("❌ Matndan audio yaratib bo‘lmadi.")

# ✅ **SRT fayl qabul qilish**
@dp.message(F.document)
async def handle_document(message: Message):
    document = message.document
    if document.file_name.endswith(".srt"):
        file_path = os.path.join(DOWNLOAD_DIR, document.file_name.replace(" ", "_"))
        await bot.download(file=document, destination=file_path)
        text = read_srt_text(file_path)
        final_audio = generate_text_audio(text)
        if final_audio:
            output_file = save_audio(final_audio)
            await message.answer_voice(FSInputFile(output_file))
        else:
            await message.answer("❌ Ushbu SRT faylni ovozga aylantirib bo‘lmadi.")
    else:
        await message.answer("⚠️ Faqat .srt formatdagi fayllarni qabul qilaman!")

    
        

# ✅ **Botni ishga tushirish**
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
