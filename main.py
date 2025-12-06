import logging
import traceback
from datetime import datetime

import telebot
from telebot import types
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    Text,
    DateTime,
)
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session, relationship

TOKEN = "8480722074:AAGJZldgfITzbZ8Efh_ChlR9dueVvAV5Itc"
# ADMIN_ID = 1
ADMIN_ID = 989084366

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TOKEN)

engine = create_engine("sqlite:///dobro.db", echo=False)
Base = declarative_base()
SessionFactory = sessionmaker(bind=engine)
Session = scoped_session(SessionFactory)


def db():
    return Session()


def escape_md(t: str):
    if not t:
        return ""
    return (
        t.replace("\\", "\\\\")
         .replace("*", "\\*")
         .replace("_", "\\_")
         .replace("`", "\\`")
         .replace("[", "\\[")
         .replace("(", "\\(")
    )


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    tg_id = Column(Integer, unique=True)
    username = Column(String)
    balance = Column(Integer, default=0)


class Activity(Base):
    __tablename__ = "activities"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    cost = Column(Integer)
    description = Column(Text)
    multiple = Column(Boolean, default=True)


class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    activity_id = Column(Integer, ForeignKey("activities.id"))
    proof_type = Column(String)
    proof_file = Column(String)
    status = Column(String, default="На проверке")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    activity = relationship("Activity")


class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    text = Column(Text)
    answer = Column(Text, nullable=True)
    status = Column(String, default="Новый")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class Poll(Base):
    __tablename__ = "polls"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    question = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    active = Column(Boolean, default=True)


class PollOption(Base):
    __tablename__ = "poll_options"
    id = Column(Integer, primary_key=True)
    poll_id = Column(Integer, ForeignKey("polls.id"))
    text = Column(String)

    poll = relationship("Poll", backref="options")


class PollAnswer(Base):
    __tablename__ = "poll_answers"
    id = Column(Integer, primary_key=True)
    poll_id = Column(Integer, ForeignKey("polls.id"))
    option_id = Column(Integer, ForeignKey("poll_options.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    poll = relationship("Poll")
    option = relationship("PollOption")
    user = relationship("User")


Base.metadata.create_all(engine)

def get_or_create_user(message):
    s = db()
    try:
        u = s.query(User).filter_by(tg_id=message.from_user.id).first()
        if not u:
            u = User(
                tg_id=message.from_user.id,
                username=message.from_user.username or "",
                balance=0
            )
            s.add(u)
            s.commit()
            logger.info(f"Создан пользователь: {u.tg_id} (@{u.username})")
        return u
    except Exception as e:
        logger.error(f"Ошибка в get_or_create_user: {e}\n{traceback.format_exc()}")
        raise
    finally:
        Session.remove()


def is_admin(message):
    return message.from_user.id == ADMIN_ID


def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("💡 Список активностей", "📤 Фиксация результата")
    kb.row("💰 Мой баланс", "❓ Задать вопрос")
    kb.row("🗳 Опросы")
    return kb


def admin_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("➕ Добавить активность", "🗑 Удалить активность")
    kb.row("📋 Все проверки", "💳 Управление балансом")
    kb.row("📦 Список активностей", "👥 Список пользователей")
    kb.row("❓ Вопросы пользователей")
    kb.row("➕ Начислить пользователю", "➖ Списать у пользователя")
    kb.row("🔄 Обнулить все балансы")
    kb.row("🗳 Управление опросами", "📊 Результаты опросов")
    kb.row("⬅ Назад")
    return kb


def back_btn():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("⬅ Назад")
    return kb


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


@bot.message_handler(func=lambda m: m.text == "⬅ Назад")
def go_back(message):
    try:
        if is_admin(message):
            bot.send_message(message.chat.id, "Главное меню администратора:", reply_markup=admin_menu())
        else:
            bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu())
    except Exception as e:
        logger.exception(f"Ошибка в go_back: {e}")


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

def admin_list_questions(message):
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

    except Exception as e:
        logger.exception(f"Ошибка в admin_list_questions: {e}")
    finally:
        Session.remove()


def admin_open_question(message):
    try:
        if message.text == "⬅ Назад":
            go_back(message)
            return

        try:
            q_id = int(message.text.split("—")[0].replace("#", "").strip())
        except:
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
            bot.register_next_step_handler(msg, lambda m: admin_answer_question(m, q.id))

        finally:
            Session.remove()
    except Exception as e:
        logger.exception(f"Ошибка в admin_open_question: {e}")


def admin_answer_question(message, q_id):
    try:
        if message.text == "⬅ Назад":
            go_back(message)
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

            logger.info(f"Ответ админа для вопроса #{q.id}: {answer}")

            bot.send_message(message.chat.id, "Ответ отправлен пользователю!", reply_markup=admin_menu())

        finally:
            Session.remove()

    except Exception as e:
        logger.exception(f"Ошибка в admin_answer_question: {e}")

@bot.message_handler(func=lambda m: m.text == "💡 Список активностей")
def list_activities(message):
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

        msg = bot.send_message(message.chat.id, "Выберите активность для просмотра:", reply_markup=kb)
        bot.register_next_step_handler(msg, show_activity_detail)

    except Exception as e:
        logger.exception(f"Ошибка в list_activities: {e}")
    finally:
        Session.remove()


def show_activity_detail(message):
    try:
        if message.text == "⬅ Назад":
            go_back(message)
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


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith(("submit_", "back_to_activities")))
def activity_detail_callbacks(call):
    try:
        data = call.data
        if data == "back_to_activities":
            bot.answer_callback_query(call.id)
            list_activities(call.message)
            return

        if data.startswith("submit_"):
            act_id = int(data.split("_")[1])
            bot.answer_callback_query(call.id, "Выбран режим отправки результата")
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            kb.row("Фото", "Текст")
            kb.add("⬅ Назад")
            msg = bot.send_message(call.message.chat.id, "Выберите тип подтверждения:", reply_markup=kb)
            bot.register_next_step_handler(msg, lambda m: get_proof(m, act_id))
    except Exception as e:
        logger.exception(f"Ошибка в activity_detail_callbacks: {e}")


def choose_activity_for_submit(message):
    try:
        if message.text == "⬅ Назад":
            go_back(message)
            return

        s = db()
        try:
            act = s.query(Activity).filter_by(title=message.text).first()
            if not act:
                bot.send_message(message.chat.id, "Неверный выбор.", reply_markup=main_menu())
                return

            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            kb.row("Фото", "Текст")
            kb.add("⬅ Назад")

            msg = bot.send_message(message.chat.id, "Выберите тип подтверждения:", reply_markup=kb)
            bot.register_next_step_handler(msg, lambda m: get_proof(m, act.id))

        finally:
            Session.remove()
    except Exception as e:
        logger.exception(f"Ошибка в choose_activity_for_submit: {e}")


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

@bot.message_handler(func=is_admin)
def admin_router(message):
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

        elif message.text == "🗳 Опросы":
            list_polls_user(message)

        elif message.text == "📋 Все проверки":
            show_all_submissions(message)

        elif message.text == "👥 Список пользователей":
            list_users(message)

        elif message.text == "💳 Управление балансом":
            msg = bot.send_message(message.chat.id, "Введите @username:", reply_markup=back_btn())
            bot.register_next_step_handler(msg, balance_choose_user)

        elif message.text == "🔄 Обнулить все балансы":
            reset_balances(message)

        elif message.text == "🗳 Управление опросами":
            admin_polls_menu(message)

        elif message.text == "➕ Начислить пользователю":
            msg = bot.send_message(message.chat.id, "Введите @username:", reply_markup=back_btn())
            bot.register_next_step_handler(msg, lambda m: change_balance_choose_user(m, mode="add"))

        elif message.text == "➖ Списать у пользователя":
            msg = bot.send_message(message.chat.id, "Введите @username:", reply_markup=back_btn())
            bot.register_next_step_handler(msg, lambda m: change_balance_choose_user(m, mode="sub"))

        else:
            bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())
    except Exception as e:
        logger.exception(f"Ошибка в admin_router: {e}")


def admin_show_poll_results(message):
    """Показать админу все опросы с результатами голосования"""
    s = db()
    try:
        polls = s.query(Poll).order_by(Poll.created_at.desc()).all()
        if not polls:
            bot.send_message(message.chat.id, "Опросов нет.", reply_markup=admin_menu())
            return

        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for p in polls:
            # Подсчитываем голоса за опрос
            vote_count = s.query(PollAnswer).filter_by(poll_id=p.id).count()
            kb.add(f"{p.id}. {p.title} ({vote_count} голосов)")
        kb.add("⬅ Назад")

        msg = bot.send_message(message.chat.id, "Выберите опрос для просмотра результатов:", reply_markup=kb)
        bot.register_next_step_handler(msg, admin_show_poll_detail)
    except Exception as e:
        logger.exception(f"Ошибка в admin_show_poll_results: {e}")
    finally:
        Session.remove()


def admin_show_poll_detail(message):
    try:
        if message.text == "⬅ Назад":
            go_back(message)
            return

        try:
            poll_id = int(message.text.split(".")[0])
        except:
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
                votes = s.query(PollAnswer).filter_by(poll_id=poll.id, option_id=option.id).count()
                results[option.text] = votes
                total_votes += votes

            # Формируем текст с результатами
            text = f"*📊 {escape_md(poll.title)}*\n"
            text += f"*{escape_md(poll.question)}*\n\n"

            if total_votes == 0:
                text += "Пока никто не голосовал."
            else:
                text += f"*Всего голосов: {total_votes}*\n\n"

                # Сортируем по количеству голосов
                sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
                for option_text, count in sorted_results:
                    percent = (count / total_votes * 100) if total_votes > 0 else 0
                    text += f"• {escape_md(option_text)}: {count} ({percent:.1f}%)\n"

            text += f"\n*Дата:* {poll.created_at.strftime('%d.%m.%Y %H:%M')}"

            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            kb.add("⬅ Назад")

            bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=kb)

        finally:
            Session.remove()
    except Exception as e:
        logger.exception(f"Ошибка в admin_show_poll_detail: {e}")


def admin_add_title(message):
    try:
        if message.text == "⬅ Назад":
            go_back(message)
            return

        title = message.text
        msg = bot.send_message(message.chat.id, "Стоимость:", reply_markup=back_btn())
        bot.register_next_step_handler(msg, lambda m: admin_add_cost(m, title))
    except Exception as e:
        logger.exception(f"Ошибка в admin_add_title: {e}")


def admin_add_cost(message, title):
    try:
        if message.text == "⬅ Назад":
            go_back(message)
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
    try:
        if message.text == "⬅ Назад":
            go_back(message)
            return

        desc = message.text
        msg = bot.send_message(message.chat.id, "Повторяемая? (да/нет)", reply_markup=back_btn())
        bot.register_next_step_handler(msg, lambda m: admin_add_multiple(m, title, cost, desc))
    except Exception as e:
        logger.exception(f"Ошибка в admin_add_desc: {e}")


def admin_add_multiple(message, title, cost, desc):
    try:
        if message.text == "⬅ Назад":
            go_back(message)
            return

        multiple = message.text.lower() == "да"

        s = db()
        try:
            a = Activity(title=title, cost=cost, description=desc, multiple=multiple)
            s.add(a)
            s.commit()
            logger.info(f"Добавлена активность: {a.id} {a.title} cost={a.cost} multiple={a.multiple}")
            bot.send_message(message.chat.id, "Добавлено!", reply_markup=admin_menu())
        finally:
            Session.remove()
    except Exception as e:
        logger.exception(f"Ошибка в admin_add_multiple: {e}")


def delete_activities(message):
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

        msg = bot.send_message(message.chat.id, "Выберите:", reply_markup=kb)
        bot.register_next_step_handler(msg, delete_activity_confirm)
    except Exception as e:
        logger.exception(f"Ошибка в delete_activities: {e}")
    finally:
        Session.remove()


def delete_activity_confirm(message):
    try:
        if message.text == "⬅ Назад":
            go_back(message)
            return

        try:
            aid = int(message.text.split(".")[0])
        except:
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
            bot.send_message(message.chat.id, "Удалено!", reply_markup=admin_menu())
        finally:
            Session.remove()
    except Exception as e:
        logger.exception(f"Ошибка в delete_activity_confirm: {e}")


def list_users(message):
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
    except Exception as e:
        logger.exception(f"Ошибка в list_users: {e}")
    finally:
        Session.remove()


def show_all_submissions(message):
    s = db()
    try:
        subs = s.query(Submission).order_by(Submission.created_at.asc()).all()

        if not subs:
            bot.send_message(message.chat.id, "Нет проверок.", reply_markup=admin_menu())
            return

        for sub in subs:
            text = (
                f"*ID {sub.id}* — *{escape_md(sub.user.username)}* → *{escape_md(sub.activity.title)}*\n"
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
                    bot.send_photo(message.chat.id, sub.proof_file, caption=text, parse_mode="Markdown", reply_markup=kb)
                except Exception:
                    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=kb)
            else:
                text += f"\n\n{escape_md(sub.proof_file)}"
                bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        logger.exception(f"Ошибка в show_all_submissions: {e}")
    finally:
        Session.remove()


@bot.callback_query_handler(func=lambda c: c.data.startswith(("accept_", "reject_")))
def check_submission(call):
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
            logger.info(f"Submission #{sub.id} принято. user={sub.user.tg_id} +{sub.activity.cost}. Новый баланс={sub.user.balance}")
            bot.answer_callback_query(call.id, "Принято! Баллы начислены.")
            try:
                bot.send_message(sub.user.tg_id, f"🎉 Ваше выполнение '{sub.activity.title}' принято! +{sub.activity.cost} коинов.")
            except Exception:
                logger.exception(f"Не удалось уведомить пользователя {sub.user.tg_id} о принятии submission {sub.id}")
        else:
            sub.status = "Отклонено"
            s.commit()
            logger.info(f"Submission #{sub.id} отклонено. user={sub.user.tg_id}")
            bot.answer_callback_query(call.id, "Отклонено.")
            try:
                bot.send_message(sub.user.tg_id, f"❌ Ваше выполнение '{sub.activity.title}' отклонено.")
            except Exception:
                logger.exception(f"Не удалось уведомить пользователя {sub.user.tg_id} о отклонении submission {sub.id}")

    except Exception as e:
        logger.exception(f"Ошибка в check_submission: {e}")
    finally:
        Session.remove()

def admin_polls_menu(message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("➕ Создать опрос", "🗑 Удалить опрос")
    kb.row("⬅ Назад")
    msg = bot.send_message(message.chat.id, "Управление опросами:", reply_markup=kb)


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


def admin_create_poll_start(message):
    msg = bot.send_message(message.chat.id, "Введите заголовок опроса:", reply_markup=back_btn())
    bot.register_next_step_handler(msg, admin_create_poll_title)


def admin_create_poll_title(message):
    try:
        if message.text == "⬅ Назад":
            go_back(message)
            return
        title = message.text
        msg = bot.send_message(message.chat.id, "Введите вопрос текста опроса:", reply_markup=back_btn())
        bot.register_next_step_handler(msg, lambda m: admin_create_poll_question(m, title))
    except Exception as e:
        logger.exception(f"Ошибка в admin_create_poll_title: {e}")


def admin_create_poll_question(message, title):
    try:
        if message.text == "⬅ Назад":
            go_back(message)
            return
        question = message.text
        msg = bot.send_message(message.chat.id, "Введите варианты через | (например: Да|Нет|Не уверен):", reply_markup=back_btn())
        bot.register_next_step_handler(msg, lambda m: admin_create_poll_options(m, title, question))
    except Exception as e:
        logger.exception(f"Ошибка в admin_create_poll_question: {e}")


def admin_create_poll_options(message, title, question):
    try:
        if message.text == "⬅ Назад":
            go_back(message)
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
            logger.info(f"Создан опрос: id={p.id} title={p.title} options={len(opts)}")
            bot.send_message(message.chat.id, "Опрос создан!", reply_markup=admin_menu())
        finally:
            Session.remove()
    except Exception as e:
        logger.exception(f"Ошибка в admin_create_poll_options: {e}")


def admin_delete_poll_start(message):
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
        msg = bot.send_message(message.chat.id, "Выберите опрос для удаления:", reply_markup=kb)
        bot.register_next_step_handler(msg, admin_delete_poll_confirm)
    except Exception as e:
        logger.exception(f"Ошибка в admin_delete_poll_start: {e}")
    finally:
        Session.remove()


def admin_delete_poll_confirm(message):
    try:
        if message.text == "⬅ Назад":
            go_back(message)
            return
        try:
            pid = int(message.text.split(".")[0])
        except:
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

def balance_choose_user(message):
    try:
        if message.text == "⬅ Назад":
            go_back(message)
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
    try:
        if message.text == "⬅ Назад":
            go_back(message)
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
            logger.info(f"Баланс установлен админом: user={user.username} ({user.tg_id}) {old} -> {user.balance}")
            bot.send_message(message.chat.id, "Обновлено!", reply_markup=admin_menu())
        finally:
            Session.remove()
    except Exception as e:
        logger.exception(f"Ошибка в balance_set: {e}")


def change_balance_choose_user(message, mode):
    try:
        if message.text == "⬅ Назад":
            go_back(message)
            return

        username = message.text.replace("@", "")
        s = db()

        try:
            user = s.query(User).filter_by(username=username).first()
            if not user:
                bot.send_message(message.chat.id, "Не найден.", reply_markup=admin_menu())
                return

            msg = bot.send_message(
                message.chat.id,
                "Введите число баллов:",
                reply_markup=back_btn()
            )
            bot.register_next_step_handler(msg, lambda m: change_balance_apply(m, user.id, mode))

        finally:
            Session.remove()
    except Exception as e:
        logger.exception(f"Ошибка в change_balance_choose_user: {e}")


def change_balance_apply(message, user_id, mode):
    try:
        if message.text == "⬅ Назад":
            go_back(message)
            return

        if not message.text.isdigit():
            msg = bot.send_message(message.chat.id, "Введите число:", reply_markup=back_btn())
            bot.register_next_step_handler(msg, lambda m: change_balance_apply(m, user_id, mode))
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
                bot.send_message(user.tg_id, f"Ваш баланс изменен администратором: {action}. Текущий баланс: {user.balance}")
            except Exception:
                logger.exception(f"Не удалось уведомить пользователя {user.tg_id} об изменении баланса")

        finally:
            Session.remove()
    except Exception as e:
        logger.exception(f"Ошибка в change_balance_apply: {e}")


def reset_balances(message):
    s = db()
    try:
        s.query(User).update({"balance": 0})
        s.commit()
        logger.info(f"Все балансы обнулены администратором {message.from_user.id}")
        bot.send_message(message.chat.id, "Все балансы обнулены!", reply_markup=admin_menu())
    except Exception as e:
        logger.exception(f"Ошибка в reset_balances: {e}")
    finally:
        Session.remove()

def submit_result_choose_activity(message):
    try:
        if message.text == "⬅ Назад":
            go_back(message)
            return

        try:
            act_id = int(message.text.split(".")[0])
        except Exception:
            bot.send_message(message.chat.id, "Неверный формат. Выберите активность из списка.", reply_markup=main_menu())
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




if __name__ == '__main__':
    try:
        logger.info("BOT RUNNING...")
        bot.infinity_polling()
    except Exception as e:
        logger.exception(f"Критическая ошибка в основном цикле: {e}")
