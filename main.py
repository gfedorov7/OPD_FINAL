"""
Telegram bot: ДОБРО.Коins
Features:
- Users: register, view balance
- Activities: admin can add/delete; users can list and view details; users can submit proof from activity detail view
- Submissions: stored and reviewed by admin (accept/reject)
- Questions: users can ask questions; saved in DB; admin can list and answer; user receives answer
- Polls: admin can create polls with options; users can list polls, vote; answers are saved

DB: SQLite via SQLAlchemy (scoped_session)

Usage:
- Replace TOKEN with your bot token
- Run: python bot.py

Documentation at the bottom of this file
"""

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
from datetime import datetime

# ---------------- SETTINGS --------------------

TOKEN = "8480722074:AAGJZldgfITzbZ8Efh_ChlR9dueVvAV5Itc"
ADMIN_ID = 989084366

bot = telebot.TeleBot(TOKEN)

# ---------------- DATABASE --------------------

engine = create_engine("sqlite:///dobro.db", echo=False)
Base = declarative_base()
SessionFactory = sessionmaker(bind=engine)
Session = scoped_session(SessionFactory)


def db():
    return Session()


# --------------- MARKDOWN ESCAPE --------------

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


# ------------------ MODELS --------------------

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


# ------------------ HELPERS -------------------

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
        return u
    finally:
        Session.remove()


def is_admin(message):
    return message.from_user.id == ADMIN_ID


# ------------------ KEYBOARDS -----------------

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
    kb.row("🔄 Обнулить все балансы")
    kb.row("⬅ Назад")
    return kb


def back_btn():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("⬅ Назад")
    return kb


# ---------------- BOT COMMANDS ----------------

@bot.message_handler(commands=["start"])
def start(message):
    get_or_create_user(message)
    bot.send_message(
        message.chat.id,
        "Добро пожаловать! ✨\nВыберите действие:",
        reply_markup=main_menu()
    )


# ---------------- MAIN MENU --------------------

@bot.message_handler(func=lambda m: m.text == "⬅ Назад")
def go_back(message):
    if is_admin(message):
        bot.send_message(message.chat.id, "Главное меню администратора:", reply_markup=admin_menu())
    else:
        bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu())


@bot.message_handler(func=lambda m: m.text == "💰 Мой баланс")
def my_balance(message):
    u = get_or_create_user(message)
    bot.send_message(
        message.chat.id,
        f"Ваш баланс: *{u.balance}* Добро-баллов",
        parse_mode="Markdown"
    )


# ------------- QUESTIONS (USER) -----------------

@bot.message_handler(func=lambda m: m.text == "❓ Задать вопрос")
def ask_question(message):
    msg = bot.send_message(message.chat.id, "Введите ваш вопрос:", reply_markup=back_btn())
    bot.register_next_step_handler(msg, save_question)


def save_question(message):
    if message.text == "⬅ Назад":
        go_back(message)
        return

    u = get_or_create_user(message)
    s = db()
    try:
        q = Question(user_id=u.id, text=message.text)
        s.add(q)
        s.commit()
    finally:
        Session.remove()

    bot.send_message(message.chat.id, "Ваш вопрос отправлен администраторам! 🙌", reply_markup=main_menu())


# ----------- QUESTIONS (ADMIN) ------------------

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

    finally:
        Session.remove()


def admin_open_question(message):
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


def admin_answer_question(message, q_id):
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

        bot.send_message(message.chat.id, "Ответ отправлен пользователю!", reply_markup=admin_menu())

    finally:
        Session.remove()


# ------------- LIST ACTIVITIES -----------------

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

    finally:
        Session.remove()


def show_activity_detail(message):
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


# ------------- FIX RESULT (via activity detail) ----------------

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith(("submit_", "back_to_activities")))
def activity_detail_callbacks(call):
    data = call.data
    if data == "back_to_activities":
        bot.answer_callback_query(call.id)
        # simulate pressing list activities
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


def choose_activity_for_submit(message):
    # kept for compatibility with older flow
    if message.text == "⬅ Назад":
        go_back(message)
        return

    s = db()
    try:
        # if user typed title, try to map
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


def get_proof(message, act_id):
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


def save_submission_photo(message, act_id):
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
    finally:
        Session.remove()

    bot.send_message(message.chat.id, "Отправлено на проверку! ⏳", reply_markup=main_menu())


def save_submission_text(message, act_id):
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
    finally:
        Session.remove()

    bot.send_message(message.chat.id, "Отправлено на проверку!", reply_markup=main_menu())


# ---------------- ADMIN ROUTER ----------------

@bot.message_handler(func=is_admin)
def admin_router(message):

    if message.text == "❓ Вопросы пользователей":
        admin_list_questions(message)

    elif message.text == "➕ Добавить активность":
        msg = bot.send_message(message.chat.id, "Название:", reply_markup=back_btn())
        bot.register_next_step_handler(msg, admin_add_title)

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

    elif message.text == "🗳 Управление опросами":
        admin_polls_menu(message)

    else:
        bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())


# ------------ ADD ACTIVITY ---------------------

def admin_add_title(message):
    if message.text == "⬅ Назад":
        go_back(message)
        return

    title = message.text
    msg = bot.send_message(message.chat.id, "Стоимость:", reply_markup=back_btn())
    bot.register_next_step_handler(msg, lambda m: admin_add_cost(m, title))


def admin_add_cost(message, title):
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


def admin_add_desc(message, title, cost):
    if message.text == "⬅ Назад":
        go_back(message)
        return

    desc = message.text
    msg = bot.send_message(message.chat.id, "Повторяемая? (да/нет)", reply_markup=back_btn())
    bot.register_next_step_handler(msg, lambda m: admin_add_multiple(m, title, cost, desc))


def admin_add_multiple(message, title, cost, desc):
    if message.text == "⬅ Назад":
        go_back(message)
        return

    multiple = message.text.lower() == "да"

    s = db()
    try:
        a = Activity(title=title, cost=cost, description=desc, multiple=multiple)
        s.add(a)
        s.commit()
        bot.send_message(message.chat.id, "Добавлено!", reply_markup=admin_menu())
    finally:
        Session.remove()


# ------------ DELETE ACTIVITY ------------------

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
    finally:
        Session.remove()


def delete_activity_confirm(message):
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
        s.delete(act)
        s.commit()
        bot.send_message(message.chat.id, "Удалено!", reply_markup=admin_menu())
    finally:
        Session.remove()


# ---------------- USERS LIST -------------------

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
    finally:
        Session.remove()


# ---------------- SUBMISSIONS ------------------

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
    finally:
        Session.remove()


# ------------ CALLBACKS ACCEPT/REJECT ----------

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
            bot.answer_callback_query(call.id, "Принято! Баллы начислены.")
            bot.send_message(sub.user.tg_id, f"🎉 Ваше выполнение '{sub.activity.title}' принято! +{sub.activity.cost} коинов.")
        else:
            sub.status = "Отклонено"
            bot.answer_callback_query(call.id, "Отклонено.")
            bot.send_message(sub.user.tg_id, f"❌ Ваше выполнение '{sub.activity.title}' отклонено.")

        s.commit()

    finally:
        Session.remove()


# ---------------- POLLS -------------------------

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
    finally:
        Session.remove()


def show_poll_detail(message):
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


def answer_poll(message, poll_id):
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
        # prevent duplicate answers: replace existing
        existing = s.query(PollAnswer).filter_by(poll_id=poll_id, user_id=user.id).first()
        if existing:
            existing.option_id = opt.id
            existing.created_at = datetime.utcnow()
        else:
            ans = PollAnswer(poll_id=poll_id, option_id=opt.id, user_id=user.id)
            s.add(ans)
        s.commit()

        bot.send_message(message.chat.id, "Спасибо за голос!", reply_markup=main_menu())
    finally:
        Session.remove()


# Admin create/delete polls

def admin_create_poll_start(message):
    msg = bot.send_message(message.chat.id, "Введите заголовок опроса:", reply_markup=back_btn())
    bot.register_next_step_handler(msg, admin_create_poll_title)


def admin_create_poll_title(message):
    if message.text == "⬅ Назад":
        go_back(message)
        return
    title = message.text
    msg = bot.send_message(message.chat.id, "Введите вопрос текста опроса:", reply_markup=back_btn())
    bot.register_next_step_handler(msg, lambda m: admin_create_poll_question(m, title))


def admin_create_poll_question(message, title):
    if message.text == "⬅ Назад":
        go_back(message)
        return
    question = message.text
    msg = bot.send_message(message.chat.id, "Введите варианты через | (например: Да|Нет|Не уверен):", reply_markup=back_btn())
    bot.register_next_step_handler(msg, lambda m: admin_create_poll_options(m, title, question))


def admin_create_poll_options(message, title, question):
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
        s.commit()  # to get id
        for o in opts:
            po = PollOption(poll_id=p.id, text=o)
            s.add(po)
        s.commit()
        bot.send_message(message.chat.id, "Опрос создан!", reply_markup=admin_menu())
    finally:
        Session.remove()


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
    finally:
        Session.remove()


def admin_delete_poll_confirm(message):
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
        # delete options and answers
        s.query(PollAnswer).filter_by(poll_id=p.id).delete()
        s.query(PollOption).filter_by(poll_id=p.id).delete()
        s.delete(p)
        s.commit()
        bot.send_message(message.chat.id, "Удалено.", reply_markup=admin_menu())
    finally:
        Session.remove()


# Hook admin poll commands from admin menu keyboard
@bot.message_handler(func=lambda m: m.text == "➕ Создать опрос")
def handle_create_poll(m):
    if not is_admin(m):
        return
    admin_create_poll_start(m)


@bot.message_handler(func=lambda m: m.text == "🗑 Удалить опрос")
def handle_delete_poll(m):
    if not is_admin(m):
        return
    admin_delete_poll_start(m)


# ------------ BALANCE CONTROL -----------------

def balance_choose_user(message):
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


def balance_set(message, user_id):
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
        user.balance = int(message.text)
        s.commit()

        bot.send_message(message.chat.id, "Обновлено!", reply_markup=admin_menu())

    finally:
        Session.remove()


# ------------ RESET BALANCES -------------------

def reset_balances(message):
    s = db()
    try:
        s.query(User).update({"balance": 0})
        s.commit()
        bot.send_message(message.chat.id, "Все балансы обнулены!", reply_markup=admin_menu())
    finally:
        Session.remove()


# ---------------- RUN --------------------------

if __name__ == '__main__':
    print("BOT RUNNING...")
    bot.infinity_polling()


# ---------------- DOCUMENTATION ----------------
"""
ДОКУМЕНТАЦИЯ (README)

1) Запуск
- Установите зависимости: pip install -r requirements.txt (telebot, sqlalchemy)
- Вставьте токен в переменную TOKEN
- python bot.py

2) Роли
- Обычный пользователь: может просматривать активности, смотреть детали активности, отправлять доказательства (фото/текст), смотреть и участвовать в опросах, задавать вопросы.
- Администратор (ADMIN_ID): может добавлять/удалять активности, просматривать и подтверждать выполнения, просматривать пользователей, управлять балансом, отвечать на вопросы, создавать/удалять опросы.

3) Функционал активности
- Меню "💡 Список активностей" показывает список. При выборе показывается детальная карточка с кнопкой "📤 Отправить результат". При отправке выбирается тип доказательства: Фото или Текст.
- Все отправления сохраняются в таблице submissions и доступны админу в разделе "📋 Все проверки".

4) Вопросы
- Пользователь: "❓ Задать вопрос" — вопрос сохраняется в таблице questions со статусом "Новый".
- Админ: "❓ Вопросы пользователей" — список вопросов, выбор вопроса, ввод ответа. Ответ сохраняется и отправляется пользователю; статус меняется на "Отвечен".

5) Опросы
- Админ: через меню управления опросами ("🗳 Управление опросами") создает опрос: заголовок, текст, варианты через |. Вопросы сохраняются в таблице polls и варианты в poll_options.
- Пользователь: меню "🗳 Опросы" — выбрать опрос → выбрать вариант. Ответы сохраняются в poll_answers. Повторное голосование перезаписывает ответ.

6) Безопасность Markdown
- Все пользовательские данные (username, тексты) экранируются перед отправкой с parse_mode="Markdown" для предотвращения ошибок.

7) Замечания и улучшения
- Можно добавить пагинацию для длинных списков активностей/вопросов/опросов.
- Добавить логирование действий и ошибок.
- Добавить ограничения доступа к функциям (например, только админ может создавать активности).

"""

