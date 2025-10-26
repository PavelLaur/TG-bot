import asyncio
import hashlib
import os
import time
from collections import Counter
from datetime import datetime
from typing import Optional

import requests
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, OPENWEATHER_API_KEY, EXCHANGE_API_KEY
from models import TaskStorage

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

task_storage = TaskStorage()

command_stats = Counter()
start_time = time.time()

# Отслеживание уникальных пользователей
unique_users = set()

TASKS_PER_PAGE = 10

def add_user(user_id: int):
    """Добавляет пользователя в множество уникальных пользователей"""
    unique_users.add(user_id)

@router.message(Command("start"))
async def start_command(message: Message):
    add_user(message.from_user.id)
    command_stats['start'] += 1
    await message.answer(
        "👋 Привет! Я УниПомощник - ваш персональный помощник.\n\n"
        "Доступные команды:\n"
        "📝 /todo - управление задачами\n"
        "🌤️ /weather <город> - погода\n"
        "💱 /rate <базовая валюта> <валюты> - курсы валют\n"
        "📁 /fileinfo - информация о файле\n"
        "📊 /stats - статистика бота\n"
        "❓ /help - помощь"
    )

@router.message(Command("help"))
async def help_command(message: Message):
    add_user(message.from_user.id)
    command_stats['help'] += 1
    await message.answer(
        "📖 Помощь по командам:\n\n"
        "📝 /todo add <текст> - добавить задачу\n"
        "📝 /todo list - показать задачи\n"
        "📝 /todo done <id> - отметить задачу выполненной\n\n"
        "🌤️ /weather Москва - узнать погоду в городе\n\n"
        "💱 /rate USD EUR,RUB - курсы валют\n\n"
        "📁 Отправьте файл и используйте /fileinfo для получения информации\n\n"
        "📊 /stats - статистика работы бота"
    )

@router.message(Command("todo"))
async def todo_command(message: Message):
    add_user(message.from_user.id)
    command_stats['todo'] += 1
    
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if not args:
        await message.answer(
            "📝 Команды для работы с задачами:\n"
            "• /todo add <текст> - добавить задачу\n"
            "• /todo list - показать задачи\n"
            "• /todo done <id> - отметить задачу выполненной"
        )
        return
    
    subcommand = args[0].lower()
    
    if subcommand == "add":
        if len(args) < 2:
            await message.answer("❌ Укажите текст задачи: /todo add <текст>")
            return
        
        task_text = " ".join(args[1:])
        task = task_storage.add_task(task_text)
        await message.answer(f"✅ Задача добавлена (ID: {task.id}): {task_text}")
    
    elif subcommand == "list":
        await show_tasks_list(message, page=0)
    
    elif subcommand == "done":
        if len(args) < 2:
            await message.answer("❌ Укажите ID задачи: /todo done <id>")
            return
        
        try:
            task_id = int(args[1])
            if task_storage.mark_done(task_id):
                await message.answer(f"✅ Задача {task_id} отмечена как выполненная")
            else:
                await message.answer(f"❌ Задача с ID {task_id} не найдена")
        except ValueError:
            await message.answer("❌ ID задачи должен быть числом")

async def show_tasks_list(message: Message, page: int = 0):
    tasks = task_storage.get_tasks(message.from_user.id)
    
    if not tasks:
        await message.answer("📝 У вас нет активных задач")
        return
    
    start_idx = page * TASKS_PER_PAGE
    end_idx = start_idx + TASKS_PER_PAGE
    page_tasks = tasks[start_idx:end_idx]
    
    text = f"📝 Ваши задачи (страница {page + 1}):\n\n"
    for task in page_tasks:
        text += f"• {task.id}. {task.text}\n"
    
    keyboard = []
    
    if page > 0:
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"tasks_page_{page-1}")])
    
    if end_idx < len(tasks):
        keyboard.append([InlineKeyboardButton("Вперед ➡️", callback_data=f"tasks_page_{page+1}")])
    
    if keyboard:
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    else:
        reply_markup = None
    
    await message.answer(text, reply_markup=reply_markup)

@router.callback_query(lambda c: c.data.startswith("tasks_page_"))
async def handle_tasks_pagination(callback: CallbackQuery):
    page = int(callback.data.split("_")[-1])
    await callback.message.edit_text("")
    await show_tasks_list(callback.message, page)
    await callback.answer()

@router.message(Command("weather"))
async def weather_command(message: Message):
    add_user(message.from_user.id)
    command_stats['weather'] += 1
    
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if not args:
        await message.answer("❌ Укажите город: /weather <город>")
        return
    
    city = " ".join(args)
    
    if not OPENWEATHER_API_KEY:
        await message.answer("❌ Сервис погоды недоступен (отсутствует API ключ)")
        return
    
    await get_weather(message, city)

async def get_weather(message: Message, city: str, retry_count: int = 3):
    url = f"http://api.openweathermap.org/data/2.5/weather"
    params = {
        'q': city,
        'appid': OPENWEATHER_API_KEY,
        'units': 'metric',
        'lang': 'ru'
    }
    
    for attempt in range(retry_count):
        try:
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                city_name = data['name']
                temp = data['main']['temp']
                description = data['weather'][0]['description']
                humidity = data['main']['humidity']
                wind_speed = data['wind']['speed']
                
                weather_text = (
                    f"🌤️ Погода в {city_name}:\n\n"
                    f"🌡️ Температура: {temp}°C\n"
                    f"☁️ Описание: {description}\n"
                    f"💧 Влажность: {humidity}%\n"
                    f"💨 Скорость ветра: {wind_speed} м/с"
                )
                
                await message.answer(weather_text)
                return
            
            elif response.status_code == 404:
                await message.answer(f"❌ Город '{city}' не найден")
                return
            
            else:
                raise Exception(f"HTTP {response.status_code}")
        
        except Exception as e:
            if attempt < retry_count - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            else:
                await message.answer(f"❌ Ошибка получения погоды: {str(e)}")

@router.message(Command("rate"))
async def rate_command(message: Message):
    add_user(message.from_user.id)
    command_stats['rate'] += 1
    
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if len(args) < 2:
        await message.answer("❌ Использование: /rate <базовая валюта> <валюты через запятую>\nПример: /rate USD EUR,RUB")
        return
    
    base_currency = args[0].upper()
    target_currencies = [curr.strip().upper() for curr in args[1].split(',')]
    
    await get_exchange_rates(message, base_currency, target_currencies)

async def get_exchange_rates(message: Message, base_currency: str, target_currencies: list):
    url = f"https://api.exchangerate-api.com/v4/latest/{base_currency}"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            rates = data.get('rates', {})
            
            if not rates:
                await message.answer(f"❌ Не удалось получить курсы для {base_currency}")
                return
            
            text = f"💱 Курсы валют (базовая: {base_currency}):\n\n"
            
            for currency in target_currencies:
                if currency in rates:
                    rate = rates[currency]
                    text += f"• {currency}: {rate:.4f}\n"
                else:
                    text += f"• {currency}: недоступна\n"
            
            await message.answer(text)
        
        else:
            await message.answer(f"❌ Ошибка получения курсов валют (HTTP {response.status_code})")
    
    except Exception as e:
        await message.answer(f"❌ Ошибка получения курсов валют: {str(e)}")

async def analyze_file(message: Message):
    command_stats['fileinfo'] += 1
    
    try:
        if message.document:
            file_info = await bot.get_file(message.document.file_id)
            file_name = message.document.file_name or "Неизвестный файл"
            file_size = message.document.file_size
            file_type = "📄 Документ"
        elif message.photo:
            file_info = await bot.get_file(message.photo[-1].file_id)
            file_name = "Фото"
            file_size = message.photo[-1].file_size
            file_type = "🖼️ Фото"
        elif message.video:
            file_info = await bot.get_file(message.video.file_id)
            file_name = message.video.file_name or "Видео"
            file_size = message.video.file_size
            file_type = "🎥 Видео"
        elif message.audio:
            file_info = await bot.get_file(message.audio.file_id)
            file_name = message.audio.file_name or "Аудио"
            file_size = message.audio.file_size
            file_type = "🎵 Аудио"
        else:
            return
        
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        
        response = requests.get(file_url)
        if response.status_code == 200:
            file_content = response.content
            sha256_hash = hashlib.sha256(file_content).hexdigest()
            
            info_text = (
                f"📁 Информация о файле:\n\n"
                f"{file_type}\n"
                f"📝 Имя файла: {file_name}\n"
                f"📏 Размер: {file_size:,} байт ({file_size/1024:.2f} КБ)\n"
                f"🔐 SHA-256: {sha256_hash}"
            )
            
            await message.answer(info_text)
        else:
            await message.answer("❌ Не удалось получить содержимое файла")
    
    except Exception as e:
        await message.answer(f"❌ Ошибка обработки файла: {str(e)}")

@router.message(lambda message: message.document or message.photo or message.video or message.audio)
async def handle_file(message: Message):
    add_user(message.from_user.id)
    await analyze_file(message)

@router.message(Command("fileinfo"))
async def fileinfo_command(message: Message):
    add_user(message.from_user.id)
    if not message.document and not message.photo and not message.video and not message.audio:
        await message.answer("❌ Отправьте файл для получения информации")
        return
    
    await analyze_file(message)

@router.message(Command("stats"))
async def stats_command(message: Message):
    add_user(message.from_user.id)
    command_stats['stats'] += 1
    
    uptime_seconds = int(time.time() - start_time)
    uptime_hours = uptime_seconds // 3600
    uptime_minutes = (uptime_seconds % 3600) // 60
    uptime_seconds = uptime_seconds % 60
    
    unique_users_count = len(unique_users)
    
    total_commands = sum(command_stats.values())
    commands_text = "\n".join([f"• {cmd}: {count}" for cmd, count in command_stats.most_common()])
    
    storage_size = task_storage.get_file_size_kb()
    
    stats_text = (
        f"📊 Статистика бота:\n\n"
        f"⏰ Время работы: {uptime_hours:02d}:{uptime_minutes:02d}:{uptime_seconds:02d}\n"
        f"👥 Уникальных пользователей: {unique_users_count}\n"
        f"📈 Всего команд выполнено: {total_commands}\n\n"
        f"📋 Статистика команд:\n{commands_text}\n\n"
        f"💾 Размер хранилища: {storage_size:.2f} КБ"
    )
    
    await message.answer(stats_text)

async def main():
    print("Bot УниПомощник запускается...")
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())