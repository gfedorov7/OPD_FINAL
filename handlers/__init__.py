from telebot import TeleBot
import logging
from . import user, polls, submissions, admin

def register_all(bot):
    user.register(bot)
    polls.register(bot)
    submissions.register(bot)
    admin.register(bot)