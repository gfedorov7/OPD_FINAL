from datetime import datetime

from telebot import types
from database.db import db, Session
from database.models import Activity, Poll, Question, PollAnswer, Submission
from keyboards.admin_kb import admin_menu
from keyboards.user_kb import main_menu, back_btn
from utils.decorators import is_admin
from utils.helpers import get_or_create_user, escape_md
import logging


logger = logging.getLogger(__name__)

def register(bot):
    @bot.message_handler(commands=["start"])
    def start(message):
        try:
            logger.info(f"/start от {message.from_user.id} (@{message.from_user.username})")
            get_or_create_user(message)
            bot.send_message(
                message.chat.id,
                "Добро пожаловать! ✨\nВыберите действие:",
                reply_markup=main_menu()
            )
        except Exception as e:
            logger.exception(f"Ошибка в start: {e}")

    @bot.message_handler(func=lambda m: m.text == "💰 Мой баланс")
    def my_balance(message):
        try:
            u = get_or_create_user(message)
            bot.send_message(
                message.chat.id,
                f"Ваш баланс: *{u.balance}* Добро-баллов",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.exception(f"Ошибка в my_balance: {e}")

    @bot.message_handler(func=lambda m: m.text == "📤 Фиксация результата")
    def submit_result_menu(message):
        try:
            s = db()
            try:
                acts = s.query(Activity).all()
                if not acts:
                    bot.send_message(message.chat.id, "Пока нет активностей ❗", reply_markup=main_menu())
                    return

                kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
                for a in acts:
                    kb.add(f"{a.id}. {a.title}")
                kb.add("⬅ Назад")

                msg = bot.send_message(message.chat.id, "Выберите активность для фиксации результата:", reply_markup=kb)
                bot.register_next_step_handler(msg, submit_result_choose_activity)
            finally:
                Session.remove()
        except Exception as e:
            logger.exception(f"Ошибка в submit_result_menu: {e}")

    def submit_result_choose_activity(message):
        try:
            if message.text == "⬅ Назад":
                go_back(message)
                return

            try:
                act_id = int(message.text.split(".")[0])
            except Exception:
                bot.send_message(message.chat.id, "Неверный формат. Выберите активность из списка.",
                                 reply_markup=main_menu())
                return

            s = db()
            try:
                act = s.query(Activity).get(act_id)
                if not act:
                    bot.send_message(message.chat.id, "Активность не найдена.", reply_markup=main_menu())
                    return
            finally:
                Session.remove()

            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            kb.row("Фото", "Текст")
            kb.add("⬅ Назад")

            msg = bot.send_message(message.chat.id, "Выберите тип подтверждения:", reply_markup=kb)
            bot.register_next_step_handler(msg, lambda m: get_proof(m, act_id))
        except Exception as e:
            logger.exception(f"Ошибка в submit_result_choose_activity: {e}")

    def get_proof(message, act_id):
        try:
            if message.text == "⬅ Назад":
                go_back(message)
                return

            proof_type = message.text

            if proof_type == "Фото":
                msg = bot.send_message(message.chat.id, "Отправьте фото:", reply_markup=back_btn())
                bot.register_next_step_handler(msg, lambda m: save_submission_photo(m, act_id))

            elif proof_type == "Текст":
                msg = bot.send_message(message.chat.id, "Введите текстовое доказательство:", reply_markup=back_btn())
                bot.register_next_step_handler(msg, lambda m: save_submission_text(m, act_id))

            else:
                bot.send_message(message.chat.id, "Ошибка выбора.", reply_markup=main_menu())
        except Exception as e:
            logger.exception(f"Ошибка в get_proof: {e}")

    def save_submission_photo(message, act_id):
        try:
            if message.text == "⬅ Назад":
                go_back(message)
                return

            if not message.photo:
                bot.send_message(message.chat.id, "Пришлите фото.", reply_markup=back_btn())
                return

            file_id = message.photo[-1].file_id
            u = get_or_create_user(message)

            s = db()
            try:
                sub = Submission(
                    user_id=u.id,
                    activity_id=act_id,
                    proof_type="photo",
                    proof_file=file_id
                )
                s.add(sub)
                s.commit()
                logger.info(f"Фото-подача: user={u.tg_id} activity={act_id} submission={sub.id}")
            finally:
                Session.remove()

            bot.send_message(message.chat.id, "Отправлено на проверку! ⏳", reply_markup=main_menu())
        except Exception as e:
            logger.exception(f"Ошибка в save_submission_photo: {e}")

    def save_submission_text(message, act_id):
        try:
            if message.text == "⬅ Назад":
                go_back(message)
                return

            u = get_or_create_user(message)

            s = db()
            try:
                sub = Submission(
                    user_id=u.id,
                    activity_id=act_id,
                    proof_type="text",
                    proof_file=message.text
                )
                s.add(sub)
                s.commit()
                logger.info(f"Текст-подача: user={u.tg_id} activity={act_id} submission={sub.id}")
            finally:
                Session.remove()

            bot.send_message(message.chat.id, "Отправлено на проверку!", reply_markup=main_menu())
        except Exception as e:
            logger.exception(f"Ошибка в save_submission_text: {e}")

    @bot.message_handler(func=lambda m: m.text == "🗳 Опросы")
    def list_polls_user(message):
        s = db()
        try:
            polls = s.query(Poll).filter_by(active=True).all()
            if not polls:
                bot.send_message(message.chat.id, "Активных опросов нет.", reply_markup=main_menu())
                return

            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for p in polls:
                kb.add(f"{p.id}. {p.title}")
            kb.add("⬅ Назад")

            msg = bot.send_message(message.chat.id, "Выберите опрос:", reply_markup=kb)
            bot.register_next_step_handler(msg, show_poll_detail)
        except Exception as e:
            logger.exception(f"Ошибка в list_polls_user: {e}")
        finally:
            Session.remove()

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
                    existing.created_at = datetime.now()
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

    @bot.message_handler(func=lambda m: m.text == "❓ Задать вопрос")
    def ask_question(message):
        try:
            msg = bot.send_message(message.chat.id, "Введите ваш вопрос:", reply_markup=back_btn())
            bot.register_next_step_handler(msg, save_question)
        except Exception as e:
            logger.exception(f"Ошибка в ask_question: {e}")

    def save_question(message):
        try:
            if message.text == "⬅ Назад":
                go_back(message)
                return

            u = get_or_create_user(message)
            s = db()
            try:
                q = Question(user_id=u.id, text=message.text)
                s.add(q)
                s.commit()
                logger.info(f"Вопрос от {u.tg_id}: {message.text}")
            finally:
                Session.remove()

            bot.send_message(message.chat.id, "Ваш вопрос отправлен администраторам! 🙌", reply_markup=main_menu())
        except Exception as e:
            logger.exception(f"Ошибка в save_question: {e}")