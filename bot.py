from telebot import TeleBot
from config import TOKEN
from database.db import init_db
from handlers import register_all


if __name__ == "__main__":
    #.env на гите, потом убрать его, тк пока тестовые данные
    bot = TeleBot(TOKEN)
    init_db()
    register_all(bot)
    bot.infinity_polling()
