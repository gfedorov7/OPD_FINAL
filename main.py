import telebot
from telebot import types
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session, relationship

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

    user = relationship("User")
    activity = relationship("Activity")


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
    return kb


def admin_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("➕ Добавить активность", "🗑 Удалить активность")
    kb.row("📋 Все проверки", "💳 Управление балансом")
    kb.row("📦 Список активностей", "👥 Список пользователей")
    kb.row("🔄 Обнулить все балансы")
    kb.row("⬅ Назад")
    return kb


def back_btn():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("⬅ Назад")
    return kb


# ----------------- BOT COMMANDS ----------------

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


# ------------- LIST ACTIVITIES -----------------

@bot.message_handler(func=lambda m: m.text == "💡 Список активностей")
def list_activities(message):
    s = db()
    try:
        acts = s.query(Activity).all()
        if not acts:
            bot.send_message(message.chat.id, "Пока нет активностей ❗", reply_markup=main_menu())
            return

        text = "*Список активностей:*\n\n"
        for a in acts:
            text += (
                f"*{escape_md(a.title)}* — {a.cost} баллов\n"
                f"{escape_md(a.description)}\n"
                f"Повторяемая: {'да' if a.multiple else 'нет'}\n\n"
            )

        bot.send_message(message.chat.id, text, parse_mode="Markdown")
    finally:
        Session.remove()


# ------------- FIX RESULT ----------------------

@bot.message_handler(func=lambda m: m.text == "📤 Фиксация результата")
def fix_result(message):
    s = db()
    try:
        acts = s.query(Activity).all()

        if not acts:
            bot.send_message(message.chat.id, "Нет активностей.", reply_markup=main_menu())
            return

        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for a in acts:
            kb.add(a.title)
        kb.add("⬅ Назад")

        msg = bot.send_message(message.chat.id, "Выберите активность:", reply_markup=kb)
        bot.register_next_step_handler(msg, choose_activity_for_submit)

    finally:
        Session.remove()


def choose_activity_for_submit(message):
    if message.text == "⬅ Назад":
        go_back(message)
        return

    s = db()
    try:
        act = s.query(Activity).filter_by(title=message.text).first()
        if not act:
            bot.send_message(message.chat.id, "Неверный выбор.", reply_markup=main_menu())
            return

        # ask proof type
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

    kb = back_btn()

    if proof_type == "Фото":
        msg = bot.send_message(message.chat.id, "Отправьте фото-доказательство:", reply_markup=kb)
        bot.register_next_step_handler(msg, lambda m: save_submission_photo(m, act_id))
    elif proof_type == "Текст":
        msg = bot.send_message(message.chat.id, "Опишите доказательство:", reply_markup=kb)
        bot.register_next_step_handler(msg, lambda m: save_submission_text(m, act_id))
    else:
        bot.send_message(message.chat.id, "Ошибка выбора.", reply_markup=main_menu())


def save_submission_photo(message, act_id):
    if message.text == "⬅ Назад":
        go_back(message)
        return

    if not message.photo:
        bot.send_message(message.chat.id, "Пришлите именно фото.", reply_markup=back_btn())
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


# ---------------- ADMIN SECTION ----------------

@bot.message_handler(func=is_admin)
def admin_router(message):

    if message.text == "⬅ Назад":
        bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())

    elif message.text == "➕ Добавить активность":
        msg = bot.send_message(message.chat.id, "Название активности:", reply_markup=back_btn())
        bot.register_next_step_handler(msg, admin_add_title)

    elif message.text == "🗑 Удалить активность":
        delete_activities(message)

    elif message.text == "📦 Список активностей":
        list_activities(message)

    elif message.text == "👥 Список пользователей":
        list_users(message)

    elif message.text == "📋 Все проверки":
        show_all_submissions(message)

    elif message.text == "💳 Управление балансом":
        msg = bot.send_message(message.chat.id, "Введите @username:", reply_markup=back_btn())
        bot.register_next_step_handler(msg, balance_choose_user)

    elif message.text == "🔄 Обнулить все балансы":
        reset_balances(message)

    else:
        bot.send_message(message.chat.id, "Меню администратора:", reply_markup=admin_menu())


# ------------ ADD ACTIVITY ---------------------

def admin_add_title(message):
    if message.text == "⬅ Назад":
        go_back(message)
        return

    title = message.text
    msg = bot.send_message(message.chat.id, "Стоимость (число):", reply_markup=back_btn())
    bot.register_next_step_handler(msg, lambda m: admin_add_cost(m, title))


def admin_add_cost(message, title):
    if message.text == "⬅ Назад":
        go_back(message)
        return

    if not message.text.isdigit():
        msg = bot.send_message(message.chat.id, "Введите число.", reply_markup=back_btn())
        bot.register_next_step_handler(msg, lambda m: admin_add_cost(m, title))
        return

    cost = int(message.text)
    msg = bot.send_message(message.chat.id, "Описание активности:", reply_markup=back_btn())
    bot.register_next_step_handler(msg, lambda m: admin_add_desc(m, title, cost))


def admin_add_desc(message, title, cost):
    if message.text == "⬅ Назад":
        go_back(message)
        return

    desc = message.text
    msg = bot.send_message(message.chat.id, "Можно выполнять многократно? (да/нет)", reply_markup=back_btn())
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
        bot.send_message(message.chat.id, "Активность добавлена!", reply_markup=admin_menu())
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
            kb.add(a.title)
        kb.add("⬅ Назад")

        msg = bot.send_message(message.chat.id, "Выберите активность для удаления:", reply_markup=kb)
        bot.register_next_step_handler(msg, delete_activity_confirm)
    finally:
        Session.remove()


def delete_activity_confirm(message):
    if message.text == "⬅ Назад":
        go_back(message)
        return

    s = db()
    try:
        act = s.query(Activity).filter_by(title=message.text).first()

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
            bot.send_message(message.chat.id, "Пользователей нет.", reply_markup=admin_menu())
            return

        text = "*Список пользователей:*\n\n"
        for u in users:
            text += f"@{escape_md(u.username)} — {u.balance} баллов\n"

        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=admin_menu())
    finally:
        Session.remove()


# ---------------- SUBMISSIONS ------------------

def show_all_submissions(message):
    s = db()
    try:
        subs = s.query(Submission).all()

        if not subs:
            bot.send_message(message.chat.id, "Нет проверок.", reply_markup=admin_menu())
            return

        for sub in subs:
            text = (
                f"*{escape_md(sub.user.username)}* → *{escape_md(sub.activity.title)}*\n"
                f"Статус: *{escape_md(sub.status)}*"
            )

            kb = types.InlineKeyboardMarkup()
            kb.add(
                types.InlineKeyboardButton("👍 Принять", callback_data=f"accept_{sub.id}"),
                types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{sub.id}")
            )

            if sub.proof_type == "photo":
                bot.send_photo(message.chat.id, sub.proof_file, caption=text, parse_mode="Markdown", reply_markup=kb)
            else:
                text += f"\n\nДоказательство:\n{escape_md(sub.proof_file)}"
                bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=kb)
    finally:
        Session.remove()


# ------------ CALLBACKS (ACCEPT / REJECT) ------

@bot.callback_query_handler(func=lambda c: c.data.startswith(("accept_", "reject_")))
def check_submission(call):
    sub_id = int(call.data.split("_")[1])
    s = db()

    try:
        sub = s.query(Submission).get(sub_id)
        if not sub:
            bot.answer_callback_query(call.id, "Ошибка: не найдено.")
            return

        if call.data.startswith("accept"):
            sub.status = "Принято"
            sub.user.balance += sub.activity.cost
            bot.answer_callback_query(call.id, "Принято! Баллы начислены.")
        else:
            sub.status = "Отклонено"
            bot.answer_callback_query(call.id, "Отклонено.")

        s.commit()

    finally:
        Session.remove()


# ---------------- BALANCE CONTROL --------------

def balance_choose_user(message):
    if message.text == "⬅ Назад":
        go_back(message)
        return

    username = message.text.replace("@", "")
    s = db()
    try:
        user = s.query(User).filter_by(username=username).first()
        if not user:
            bot.send_message(message.chat.id, "Пользователь не найден.", reply_markup=admin_menu())
            return

        msg = bot.send_message(message.chat.id, "Введите новое значение баланса:", reply_markup=back_btn())
        bot.register_next_step_handler(msg, lambda m: balance_set(m, user.id))

    finally:
        Session.remove()


def balance_set(message, user_id):
    if message.text == "⬅ Назад":
        go_back(message)
        return

    if not message.text.isdigit():
        msg = bot.send_message(message.chat.id, "Введите цифру:", reply_markup=back_btn())
        bot.register_next_step_handler(msg, lambda m: balance_set(m, user_id))
        return

    s = db()
    try:
        user = s.query(User).get(user_id)
        if not user:
            bot.send_message(message.chat.id, "Пользователь не найден.", reply_markup=admin_menu())
            return

        user.balance = int(message.text)
        s.commit()

        bot.send_message(message.chat.id, "Баланс обновлён!", reply_markup=admin_menu())

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


# --------------- RUN ---------------------------

print("BOT RUNNING...")
bot.infinity_polling()
