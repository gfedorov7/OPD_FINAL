from telebot import types

def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📤 Фиксация результата")
    kb.row("💰 Мой баланс", "❓ Задать вопрос")
    kb.row("🗳 Опросы")
    return kb

def back_btn():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("⬅ Назад")
    return kb
