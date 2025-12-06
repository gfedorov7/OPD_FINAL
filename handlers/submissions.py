from telebot import types
from database.db import db, Session
from database.models import Activity, Submission, User
from keyboards.user_kb import main_menu, back_btn
from utils.helpers import get_or_create_user, escape_md
import logging

logger = logging.getLogger(__name__)

def register(bot):
    def show_activity_detail(message):
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu())
                return

            try:
                act_id = int(message.text.split(".")[0])
            except:
                bot.send_message(message.chat.id, "Неверный формат. Выберите из списка.", reply_markup=main_menu())
                return

            s = db()
            try:
                a = s.query(Activity).get(act_id)
                if not a:
                    bot.send_message(message.chat.id, "Активность не найдена.", reply_markup=main_menu())
                    return

                text = (
                    f"*{escape_md(a.title)}*\n"
                    f"Стоимость: {a.cost} баллов\n"
                    f"Повторяемая: {'да' if a.multiple else 'нет'}\n\n"
                    f"{escape_md(a.description)}"
                )

                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton("📤 Отправить результат", callback_data=f"submit_{a.id}"))
                kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="back_to_activities"))

                bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=kb)

            finally:
                Session.remove()
        except Exception as e:
            logger.exception(f"Ошибка в show_activity_detail: {e}")

    def submit_result_choose_activity(message):
        """Выбор активности из меню 'Фиксация результата' (вызывается из user.py)"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu())
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
        """Выбор типа доказательства (Фото/Текст)"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu())
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
        """Сохранить фото-доказательство"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu())
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
        """Сохранить текстовое доказательство"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu())
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

    # ✅ CALLBACK ОБРАБОТЧИКИ ДЛЯ INLINE КНОПОК
    @bot.callback_query_handler(func=lambda c: c.data.startswith(("submit_", "back_to_activities")))
    def activity_detail_callbacks(call):
        try:
            data = call.data
            if data == "back_to_activities":
                bot.answer_callback_query(call.id)
                bot.send_message(call.message.chat.id, "💡 Список активностей:", reply_markup=main_menu())
                return

            if data.startswith("submit_"):
                act_id = int(data.split("_")[1])
                bot.answer_callback_query(call.id, "Выберите тип подтверждения")
                kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
                kb.row("Фото", "Текст")
                kb.add("⬅ Назад")
                msg = bot.send_message(call.message.chat.id, "Выберите тип подтверждения:", reply_markup=kb)
                bot.register_next_step_handler(msg, lambda m: get_proof(m, act_id))
        except Exception as e:
            logger.exception(f"Ошибка в activity_detail_callbacks: {e}")
