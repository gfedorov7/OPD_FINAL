from telebot import types
from database.db import db, Session
from database.models import User, Activity, Submission, Question, Poll, PollOption, PollAnswer
from keyboards.admin_kb import admin_menu
from keyboards.user_kb import back_btn
from utils.helpers import escape_md, get_or_create_user
from utils.decorators import is_admin
from config import ADMIN_ID
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def register(bot):
    @bot.message_handler(func=is_admin)
    def admin_router(message):
        """Главный роутер админ-команд"""
        try:
            if message.text == "❓ Вопросы пользователей":
                admin_list_questions(message)

            elif message.text == "➕ Добавить активность":
                msg = bot.send_message(message.chat.id, "Название:", reply_markup=back_btn())
                bot.register_next_step_handler(msg, admin_add_title)

            elif message.text == "📊 Результаты опросов":
                admin_show_poll_results(message)

            elif message.text == "🗳 Управление опросами":
                admin_polls_menu(message)

            elif message.text == "➕ Создать опрос":
                admin_create_poll_start(message)

            elif message.text == "🗑 Удалить опрос":
                admin_delete_poll_start(message)

            elif message.text == "🗑 Удалить активность":
                delete_activities(message)

            elif message.text == "📦 Список активностей":
                list_activities(message)

            elif message.text == "📋 Все проверки":
                show_all_submissions(message)

            elif message.text == "👥 Список пользователей":
                list_users(message)

            elif message.text == "💳 Управление балансом":
                msg = bot.send_message(message.chat.id, "Введите @username:", reply_markup=back_btn())
                bot.register_next_step_handler(msg, balance_choose_user)

            elif message.text == "🔄 Обнулить все балансы":
                reset_balances(message)

            elif message.text == "➕ Начислить пользователю":
                msg = bot.send_message(message.chat.id, "Введите @username:", reply_markup=back_btn())
                bot.register_next_step_handler(
                    msg, lambda m: change_balance_choose_user(m, mode="add")
                )

            elif message.text == "➖ Списать у пользователя":
                msg = bot.send_message(message.chat.id, "Введите @username:", reply_markup=back_btn())
                bot.register_next_step_handler(
                    msg, lambda m: change_balance_choose_user(m, mode="sub")
                )

            else:
                bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())
        except Exception as e:
            logger.exception(f"Ошибка в admin_router: {e}")

    # ---------------- ВОПРОСЫ ПОЛЬЗОВАТЕЛЕЙ ----------------

    def admin_list_questions(message):
        """Список вопросов пользователей"""
        s = db()
        try:
            qs = s.query(Question).all()
            if not qs:
                bot.send_message(message.chat.id, "Вопросов нет.", reply_markup=admin_menu())
                return

            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for q in qs:
                label = f"#{q.id} — {q.user.username or 'без ника'} ({q.status})"
                kb.add(label)
            kb.add("⬅ Назад")

            msg = bot.send_message(message.chat.id, "Выберите вопрос:", reply_markup=kb)
            bot.register_next_step_handler(msg, admin_open_question)
        finally:
            Session.remove()

    def admin_open_question(message):
        """Открыть вопрос для ответа"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())
                return

            try:
                q_id = int(message.text.split("—")[0].replace("#", "").strip())
            except Exception:
                bot.send_message(message.chat.id, "Некорректный выбор.", reply_markup=admin_menu())
                return

            s = db()
            try:
                q = s.query(Question).get(q_id)
                if not q:
                    bot.send_message(message.chat.id, "Вопрос не найден.", reply_markup=admin_menu())
                    return

                text = (
                    f"*Вопрос #{q.id}*\n"
                    f"От: @{escape_md(q.user.username)}\n"
                    f"Статус: {q.status}\n\n"
                    f"*Текст:* {escape_md(q.text)}"
                )

                bot.send_message(message.chat.id, text, parse_mode="Markdown")

                msg = bot.send_message(message.chat.id, "Введите ответ:", reply_markup=back_btn())
                bot.register_next_step_handler(msg, lambda m: admin_answer_question(m, q_id))
            finally:
                Session.remove()
        except Exception as e:
            logger.exception(f"Ошибка в admin_open_question: {e}")

    def admin_answer_question(message, q_id):
        """Отправить ответ на вопрос"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())
                return

            answer = message.text
            s = db()
            try:
                q = s.query(Question).get(q_id)
                if not q:
                    bot.send_message(message.chat.id, "Ошибка вопроса.", reply_markup=admin_menu())
                    return

                q.answer = answer
                q.status = "Отвечен"
                s.commit()

                bot.send_message(q.user.tg_id, f"Ответ администратора:\n\n{answer}")
                logger.info(f"Ответ админа для вопроса #{q.id}")

                bot.send_message(message.chat.id, "✅ Ответ отправлен!", reply_markup=admin_menu())
            finally:
                Session.remove()
        except Exception as e:
            logger.exception(f"Ошибка в admin_answer_question: {e}")

    # ---------------- АКТИВНОСТИ ----------------

    def admin_add_title(message):
        """Шаг 1: ввод названия активности"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())
                return
            title = message.text
            msg = bot.send_message(message.chat.id, "Стоимость:", reply_markup=back_btn())
            bot.register_next_step_handler(msg, lambda m: admin_add_cost(m, title))
        except Exception as e:
            logger.exception(f"Ошибка в admin_add_title: {e}")

    def admin_add_cost(message, title):
        """Шаг 2: ввод стоимости активности"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())
                return

            if not message.text.isdigit():
                msg = bot.send_message(message.chat.id, "Введите число:", reply_markup=back_btn())
                bot.register_next_step_handler(msg, lambda m: admin_add_cost(m, title))
                return

            cost = int(message.text)
            msg = bot.send_message(message.chat.id, "Описание:", reply_markup=back_btn())
            bot.register_next_step_handler(msg, lambda m: admin_add_desc(m, title, cost))
        except Exception as e:
            logger.exception(f"Ошибка в admin_add_cost: {e}")

    def admin_add_desc(message, title, cost):
        """Шаг 3: ввод описания активности"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())
                return

            desc = message.text
            msg = bot.send_message(message.chat.id, "Повторяемая? (да/нет)", reply_markup=back_btn())
            bot.register_next_step_handler(msg, lambda m: admin_add_multiple(m, title, cost, desc))
        except Exception as e:
            logger.exception(f"Ошибка в admin_add_desc: {e}")

    def admin_add_multiple(message, title, cost, desc):
        """Шаг 4: флаг повторяемости активности"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())
                return

            multiple = message.text.lower() == "да"

            s = db()
            try:
                a = Activity(title=title, cost=cost, description=desc, multiple=multiple)
                s.add(a)
                s.commit()
                logger.info(
                    f"Добавлена активность: {a.id} {a.title} cost={a.cost} multiple={a.multiple}"
                )
                bot.send_message(message.chat.id, "✅ Добавлено!", reply_markup=admin_menu())
            finally:
                Session.remove()
        except Exception as e:
            logger.exception(f"Ошибка в admin_add_multiple: {e}")

    def list_activities(message):
        """Список активностей для админа (просмотр)"""
        s = db()
        try:
            acts = s.query(Activity).all()
            if not acts:
                bot.send_message(message.chat.id, "Пока нет активностей ❗", reply_markup=admin_menu())
                return

            text = "*Список активностей:*\n\n"
            for a in acts:
                text += f"{a.id}. {escape_md(a.title)} — {a.cost} баллов\n"

            bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=admin_menu())
        finally:
            Session.remove()

    def delete_activities(message):
        """Старт удаления активности"""
        s = db()
        try:
            acts = s.query(Activity).all()
            if not acts:
                bot.send_message(message.chat.id, "Нет активностей!", reply_markup=admin_menu())
                return

            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for a in acts:
                kb.add(f"{a.id}. {a.title}")
            kb.add("⬅ Назад")

            msg = bot.send_message(message.chat.id, "Выберите активность для удаления:", reply_markup=kb)
            bot.register_next_step_handler(msg, delete_activity_confirm)
        finally:
            Session.remove()

    def delete_activity_confirm(message):
        """Подтверждение удаления активности"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())
                return

            try:
                aid = int(message.text.split(".")[0])
            except Exception:
                bot.send_message(message.chat.id, "Некорректный выбор.", reply_markup=admin_menu())
                return

            s = db()
            try:
                act = s.query(Activity).get(aid)
                if not act:
                    bot.send_message(message.chat.id, "Не найдено.", reply_markup=admin_menu())
                    return
                logger.info(f"Удаление активности: id={act.id} title={act.title}")
                s.delete(act)
                s.commit()
                bot.send_message(message.chat.id, "✅ Удалено!", reply_markup=admin_menu())
            finally:
                Session.remove()
        except Exception as e:
            logger.exception(f"Ошибка в delete_activity_confirm: {e}")

    # ---------------- ПОЛЬЗОВАТЕЛИ И БАЛАНСЫ ----------------

    def list_users(message):
        """Список пользователей и их балансов"""
        s = db()
        try:
            users = s.query(User).all()
            if not users:
                bot.send_message(message.chat.id, "Пусто.", reply_markup=admin_menu())
                return

            text = "*Пользователи:*\n\n"
            for u in users:
                text += f"@{escape_md(u.username)} — {u.balance} баллов\n"

            bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=admin_menu())
        finally:
            Session.remove()

    def balance_choose_user(message):
        """Выбор пользователя для установки баланса"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())
                return

            username = message.text.replace("@", "")
            s = db()
            try:
                user = s.query(User).filter_by(username=username).first()
                if not user:
                    bot.send_message(message.chat.id, "Не найден.", reply_markup=admin_menu())
                    return

                msg = bot.send_message(message.chat.id, "Введите новый баланс:", reply_markup=back_btn())
                bot.register_next_step_handler(msg, lambda m: balance_set(m, user.id))
            finally:
                Session.remove()
        except Exception as e:
            logger.exception(f"Ошибка в balance_choose_user: {e}")

    def balance_set(message, user_id):
        """Установка конкретного баланса пользователю"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())
                return

            if not message.text.isdigit():
                msg = bot.send_message(message.chat.id, "Введите число:", reply_markup=back_btn())
                bot.register_next_step_handler(msg, lambda m: balance_set(m, user_id))
                return

            s = db()
            try:
                user = s.query(User).get(user_id)
                old = user.balance
                user.balance = int(message.text)
                s.commit()
                logger.info(
                    f"Баланс установлен админом: user={user.username} ({user.tg_id}) "
                    f"{old} -> {user.balance}"
                )
                bot.send_message(message.chat.id, "Обновлено!", reply_markup=admin_menu())
            finally:
                Session.remove()
        except Exception as e:
            logger.exception(f"Ошибка в balance_set: {e}")

    def change_balance_choose_user(message, mode):
        """Выбор пользователя для изменения баланса (прибавить/списать)"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())
                return

            username = message.text.replace("@", "")
            s = db()
            try:
                user = s.query(User).filter_by(username=username).first()
                if not user:
                    bot.send_message(message.chat.id, "Не найден.", reply_markup=admin_menu())
                    return

                msg = bot.send_message(
                    message.chat.id, "Введите число баллов:", reply_markup=back_btn()
                )
                bot.register_next_step_handler(
                    msg, lambda m: change_balance_apply(m, user.id, mode)
                )
            finally:
                Session.remove()
        except Exception as e:
            logger.exception(f"Ошибка в change_balance_choose_user: {e}")

    def change_balance_apply(message, user_id, mode):
        """Применение изменения баланса"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())
                return

            if not message.text.isdigit():
                msg = bot.send_message(message.chat.id, "Введите число:", reply_markup=back_btn())
                bot.register_next_step_handler(
                    msg, lambda m: change_balance_apply(m, user_id, mode)
                )
                return

            amount = int(message.text)
            s = db()
            try:
                user = s.query(User).get(user_id)
                old_balance = user.balance

                if mode == "add":
                    user.balance += amount
                    action = f"начислено +{amount}"
                else:
                    user.balance = max(0, user.balance - amount)
                    action = f"списано -{amount}"

                s.commit()

                logger.info(
                    f"Изменение баланса пользователя {user.username} ({user.tg_id}): "
                    f"{old_balance} → {user.balance} ({action})"
                )

                bot.send_message(
                    message.chat.id,
                    f"Баланс обновлён!\nНовый баланс: {user.balance}",
                    reply_markup=admin_menu()
                )

                try:
                    bot.send_message(
                        user.tg_id,
                        f"Ваш баланс изменен администратором: {action}. "
                        f"Текущий баланс: {user.balance}"
                    )
                except Exception:
                    logger.exception(
                        f"Не удалось уведомить пользователя {user.tg_id} об изменении баланса"
                    )
            finally:
                Session.remove()
        except Exception as e:
            logger.exception(f"Ошибка в change_balance_apply: {e}")

    def reset_balances(message):
        """Обнулить все балансы"""
        s = db()
        try:
            s.query(User).update({"balance": 0})
            s.commit()
            logger.info(f"Все балансы обнулены администратором {message.from_user.id}")
            bot.send_message(message.chat.id, "Все балансы обнулены!", reply_markup=admin_menu())
        finally:
            Session.remove()

    # ---------------- ПРОВЕРКИ SUBMISSION'ОВ ----------------

    def show_all_submissions(message):
        """Показать все проверки"""
        s = db()
        try:
            subs = s.query(Submission).order_by(Submission.created_at.asc()).all()
            if not subs:
                bot.send_message(message.chat.id, "Нет проверок.", reply_markup=admin_menu())
                return

            for sub in subs:
                text = (
                    f"*ID {sub.id}* — *{escape_md(sub.user.username)}* → "
                    f"*{escape_md(sub.activity.title)}*\n"
                    f"Статус: *{escape_md(sub.status)}*\n"
                    f"Дата: {sub.created_at.strftime('%Y-%m-%d %H:%M')}"
                )

                kb = types.InlineKeyboardMarkup()
                kb.add(
                    types.InlineKeyboardButton("👍 Принять", callback_data=f"accept_{sub.id}"),
                    types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{sub.id}")
                )

                if sub.proof_type == "photo":
                    try:
                        bot.send_photo(
                            message.chat.id,
                            sub.proof_file,
                            caption=text,
                            parse_mode="Markdown",
                            reply_markup=kb
                        )
                    except Exception:
                        bot.send_message(
                            message.chat.id, text, parse_mode="Markdown", reply_markup=kb
                        )
                else:
                    text += f"\n\n{escape_md(sub.proof_file)}"
                    bot.send_message(
                        message.chat.id, text, parse_mode="Markdown", reply_markup=kb
                    )
        finally:
            Session.remove()

    @bot.callback_query_handler(func=lambda c: c.data.startswith(("accept_", "reject_")))
    def check_submission(call):
        """Callback-обработчик для Принять/Отклонить"""
        sub_id = int(call.data.split("_")[1])
        s = db()
        try:
            sub = s.query(Submission).get(sub_id)
            if not sub:
                bot.answer_callback_query(call.id, "Ошибка.")
                return

            if call.data.startswith("accept"):
                sub.status = "Принято"
                sub.user.balance += sub.activity.cost
                s.commit()
                logger.info(
                    f"Submission #{sub.id} принято. user={sub.user.tg_id} "
                    f"+{sub.activity.cost}. Новый баланс={sub.user.balance}"
                )
                bot.answer_callback_query(call.id, "✅ Принято! Баллы начислены.")
                try:
                    bot.send_message(
                        sub.user.tg_id,
                        f"🎉 Ваше выполнение '{sub.activity.title}' принято! "
                        f"+{sub.activity.cost} коинов."
                    )
                except Exception:
                    logger.exception(
                        f"Не удалось уведомить пользователя {sub.user.tg_id} "
                        f"о принятии submission {sub.id}"
                    )
            else:
                sub.status = "Отклонено"
                s.commit()
                logger.info(f"Submission #{sub.id} отклонено. user={sub.user.tg_id}")
                bot.answer_callback_query(call.id, "❌ Отклонено.")
                try:
                    bot.send_message(
                        sub.user.tg_id,
                        f"❌ Ваше выполнение '{sub.activity.title}' отклонено."
                    )
                except Exception:
                    logger.exception(
                        f"Не удалось уведомить пользователя {sub.user.tg_id} "
                        f"о отклонении submission {sub.id}"
                    )
        except Exception as e:
            logger.exception(f"Ошибка в check_submission: {e}")
        finally:
            Session.remove()

    # ---------------- ОПРОСЫ (АДМИН) ----------------

    def admin_polls_menu(message):
        """Меню управления опросами"""
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row("➕ Создать опрос", "🗑 Удалить опрос")
        kb.row("⬅ Назад")
        bot.send_message(message.chat.id, "Управление опросами:", reply_markup=kb)

    def admin_create_poll_start(message):
        """Старт создания опроса"""
        msg = bot.send_message(message.chat.id, "Введите заголовок опроса:", reply_markup=back_btn())
        bot.register_next_step_handler(msg, admin_create_poll_title)

    def admin_create_poll_title(message):
        """Заголовок опроса"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())
                return
            title = message.text
            msg = bot.send_message(message.chat.id, "Введите текст вопроса опроса:", reply_markup=back_btn())
            bot.register_next_step_handler(msg, lambda m: admin_create_poll_question(m, title))
        except Exception as e:
            logger.exception(f"Ошибка в admin_create_poll_title: {e}")

    def admin_create_poll_question(message, title):
        """Текст вопроса опроса"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())
                return
            question = message.text
            msg = bot.send_message(
                message.chat.id,
                "Введите варианты через | (например: Да|Нет|Не уверен):",
                reply_markup=back_btn()
            )
            bot.register_next_step_handler(
                msg, lambda m: admin_create_poll_options(m, title, question)
            )
        except Exception as e:
            logger.exception(f"Ошибка в admin_create_poll_question: {e}")

    def admin_create_poll_options(message, title, question):
        """Варианты ответа опроса"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())
                return

            opts = [o.strip() for o in message.text.split("|") if o.strip()]
            if not opts:
                bot.send_message(message.chat.id, "Нужны варианты.", reply_markup=admin_menu())
                return

            s = db()
            try:
                p = Poll(title=title, question=question)
                s.add(p)
                s.commit()
                for o in opts:
                    po = PollOption(poll_id=p.id, text=o)
                    s.add(po)
                s.commit()
                logger.info(
                    f"Создан опрос: id={p.id} title={p.title} options={len(opts)}"
                )
                bot.send_message(message.chat.id, "Опрос создан!", reply_markup=admin_menu())
            finally:
                Session.remove()
        except Exception as e:
            logger.exception(f"Ошибка в admin_create_poll_options: {e}")

    def admin_delete_poll_start(message):
        """Старт удаления опроса"""
        s = db()
        try:
            polls = s.query(Poll).all()
            if not polls:
                bot.send_message(message.chat.id, "Опросов нет.", reply_markup=admin_menu())
                return
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for p in polls:
                kb.add(f"{p.id}. {p.title}")
            kb.add("⬅ Назад")
            msg = bot.send_message(
                message.chat.id, "Выберите опрос для удаления:", reply_markup=kb
            )
            bot.register_next_step_handler(msg, admin_delete_poll_confirm)
        finally:
            Session.remove()

    def admin_delete_poll_confirm(message):
        """Подтверждение удаления опроса"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())
                return
            try:
                pid = int(message.text.split(".")[0])
            except Exception:
                bot.send_message(message.chat.id, "Неверный выбор.", reply_markup=admin_menu())
                return

            s = db()
            try:
                p = s.query(Poll).get(pid)
                if not p:
                    bot.send_message(message.chat.id, "Не найден.", reply_markup=admin_menu())
                    return
                logger.info(f"Удаление опроса id={p.id} title={p.title}")
                s.query(PollAnswer).filter_by(poll_id=p.id).delete()
                s.query(PollOption).filter_by(poll_id=p.id).delete()
                s.delete(p)
                s.commit()
                bot.send_message(message.chat.id, "Удалено.", reply_markup=admin_menu())
            finally:
                Session.remove()
        except Exception as e:
            logger.exception(f"Ошибка в admin_delete_poll_confirm: {e}")

    def admin_show_poll_results(message):
        """Список опросов с количеством голосов"""
        s = db()
        try:
            polls = s.query(Poll).order_by(Poll.created_at.desc()).all()
            if not polls:
                bot.send_message(message.chat.id, "Опросов нет.", reply_markup=admin_menu())
                return

            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for p in polls:
                vote_count = s.query(PollAnswer).filter_by(poll_id=p.id).count()
                kb.add(f"{p.id}. {p.title} ({vote_count} голосов)")
            kb.add("⬅ Назад")

            msg = bot.send_message(
                message.chat.id,
                "Выберите опрос для просмотра результатов:",
                reply_markup=kb
            )
            bot.register_next_step_handler(msg, admin_show_poll_detail)
        finally:
            Session.remove()

    def admin_show_poll_detail(message):
        """Детальная статистика по опросу"""
        try:
            if message.text == "⬅ Назад":
                bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())
                return

            try:
                poll_id = int(message.text.split(".")[0])
            except Exception:
                bot.send_message(message.chat.id, "Неверный выбор.", reply_markup=admin_menu())
                return

            s = db()
            try:
                poll = s.query(Poll).get(poll_id)
                if not poll:
                    bot.send_message(message.chat.id, "Опрос не найден.", reply_markup=admin_menu())
                    return

                results = {}
                total_votes = 0
                for option in poll.options:
                    votes = s.query(PollAnswer).filter_by(
                        poll_id=poll.id, option_id=option.id
                    ).count()
                    results[option.text] = votes
                    total_votes += votes

                text = f"*📊 {escape_md(poll.title)}*\n"
                text += f"*{escape_md(poll.question)}*\n\n"

                if total_votes == 0:
                    text += "Пока никто не голосовал."
                else:
                    text += f"*Всего голосов: {total_votes}*\n\n"
                    sorted_results = sorted(
                        results.items(), key=lambda x: x[1], reverse=True
                    )
                    for option_text, count in sorted_results:
                        percent = (count / total_votes * 100) if total_votes > 0 else 0
                        text += (
                            f"• {escape_md(option_text)}: "
                            f"{count} ({percent:.1f}%)\n"
                        )

                text += f"\n*Дата:* {poll.created_at.strftime('%d.%m.%Y %H:%M')}"

                kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
                kb.add("⬅ Назад")

                bot.send_message(
                    message.chat.id, text, parse_mode="Markdown", reply_markup=kb
                )
            finally:
                Session.remove()
        except Exception as e:
            logger.exception(f"Ошибка в admin_show_poll_detail: {e}")
