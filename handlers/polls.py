from telebot import types
from database.db import db, Session
from database.models import Poll, PollOption, PollAnswer, User
from keyboards.admin_kb import admin_menu
from keyboards.user_kb import main_menu, back_btn
from utils.decorators import is_admin
from utils.helpers import get_or_create_user, escape_md
import logging
from datetime import datetime


logger = logging.getLogger(__name__)

def register(bot):
    def show_poll_detail(message):
        try:
            if message.text == "⬅ Назад":
                go_back(message)
                return

            try:
                pid = int(message.text.split(".")[0])
            except:
                bot.send_message(message.chat.id, "Неверный выбор.", reply_markup=main_menu())
                return

            s = db()
            try:
                p = s.query(Poll).get(pid)
                if not p:
                    bot.send_message(message.chat.id, "Опрос не найден.", reply_markup=main_menu())
                    return

                text = f"*{escape_md(p.title)}*\n{escape_md(p.question)}"
                kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
                for o in p.options:
                    kb.add(o.text)
                kb.add("⬅ Назад")

                msg = bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=kb)
                bot.register_next_step_handler(msg, lambda m: answer_poll(m, p.id))
            finally:
                Session.remove()
        except Exception as e:
            logger.exception(f"Ошибка в show_poll_detail: {e}")

    #нарушение dry, но пришлось, иначе ошибка импортов
    @bot.message_handler(func=lambda m: m.text == "⬅ Назад")
    def go_back(message):
        try:
            if is_admin(message):
                bot.send_message(message.chat.id, "Главное меню администратора:", reply_markup=admin_menu())
            else:
                bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu())
        except Exception as e:
            logger.exception(f"Ошибка в go_back: {e}")

    def answer_poll(message, poll_id):
        try:
            if message.text == "⬅ Назад":
                go_back(message)
                return

            s = db()
            try:
                p = s.query(Poll).get(poll_id)
                if not p:
                    bot.send_message(message.chat.id, "Опрос не найден.", reply_markup=main_menu())
                    return

                opt = None
                for o in p.options:
                    if o.text == message.text:
                        opt = o
                        break

                if not opt:
                    bot.send_message(message.chat.id, "Неверный ответ.", reply_markup=main_menu())
                    return

                user = get_or_create_user(message)
                existing = s.query(PollAnswer).filter_by(poll_id=poll_id, user_id=user.id).first()
                if existing:
                    existing.option_id = opt.id
                    existing.created_at = datetime.utcnow()
                else:
                    ans = PollAnswer(poll_id=poll_id, option_id=opt.id, user_id=user.id)
                    s.add(ans)
                s.commit()

                logger.info(f"Голос: user={user.tg_id} poll={p.id} option={opt.id}")

                bot.send_message(message.chat.id, "Спасибо за голос!", reply_markup=main_menu())
            finally:
                Session.remove()
        except Exception as e:
            logger.exception(f"Ошибка в answer_poll: {e}")
