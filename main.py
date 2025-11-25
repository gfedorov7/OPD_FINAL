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
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

"""Кароч мне без разницы я токен и айди не спрятал
качаем зависимость pip install -r requirements.txt
python main.py и все воркинг"""

TOKEN = "8480722074:AAGJZldgfITzbZ8Efh_ChlR9dueVvAV5Itc"
ADMIN_ID = 989084366

bot = telebot.TeleBot(TOKEN)

engine = create_engine("sqlite:///dobro.db", echo=False)
Base = declarative_base()
Session = sessionmaker(bind=engine)
session = Session()


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


def is_admin(message):
    print(message.from_user.id)
    print(ADMIN_ID)
    return message.from_user.id == ADMIN_ID


def get_or_create_user(message):
    user = session.query(User).filter_by(tg_id=message.from_user.id).first()
    if not user:
        user = User(
            tg_id=message.from_user.id,
            username=message.from_user.username,
            balance=0,
        )
        session.add(user)
        session.commit()
    return user


def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💡 Список активностей", "📤 Фиксация результата")
    kb.add("💰 Мой баланс", "❓ Задать вопрос")
    return kb


def admin_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Добавить активность", "🗑 Удалить активность")
    kb.add("📋 Все проверки", "💳 Управление балансом")
    kb.add("🔄 Обнулить все балансы")
    kb.add("📦 Список активностей", "👥 Список пользователей")
    kb.add("⬅ В главное меню")
    return kb


@bot.message_handler(commands=["start"])
def start(message):
    get_or_create_user(message)

    if is_admin(message):
        bot.send_message(message.chat.id, "Добро пожаловать, админ!", reply_markup=admin_menu())
    else:
        bot.send_message(
            message.chat.id,
            "Добро пожаловать в программу ДОБРО.КОины!",
            reply_markup=main_menu(),
        )


@bot.message_handler(func=lambda m: m.text in ["💡 Список активностей", "📦 Список активностей"])
def show_activities(message):
    acts = session.query(Activity).all()
    if not acts:
        bot.send_message(message.chat.id, "Активности отсутствуют.")
        return

    text = "📋 *Активности:* \n\n"
    for a in acts:
        text += (
            f"*{a.id}. {a.title}*\n"
            f"Стоимость: {a.cost} коинов\n"
            f"{a.description}\n"
            f"Многократное выполнение: {'Да' if a.multiple else 'Нет'}\n\n"
        )

    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "💰 Мой баланс")
def my_balance(message):
    user = get_or_create_user(message)
    bot.send_message(
        message.chat.id,
        f"Ваш баланс: *{user.balance} ДОБРО.Коин*",
        parse_mode="Markdown",
    )


@bot.message_handler(func=lambda m: m.text == "❓ Задать вопрос")
def ask_question(message):
    msg = bot.send_message(message.chat.id, "Введите ваш вопрос:")
    bot.register_next_step_handler(msg, save_question)


def save_question(message):
    bot.send_message(ADMIN_ID, f"❓ Вопрос от @{message.from_user.username}:\n{message.text}")
    bot.send_message(message.chat.id, "Ваш вопрос отправлен организаторам!")


@bot.message_handler(func=lambda m: m.text == "📤 Фиксация результата")
def fix_result(message):
    acts = session.query(Activity).all()
    if not acts:
        bot.send_message(message.chat.id, "Нет активностей.")
        return

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for a in acts:
        kb.add(f"{a.id}. {a.title}")

    msg = bot.send_message(message.chat.id, "Выберите активность:", reply_markup=kb)
    bot.register_next_step_handler(msg, choose_activity)


def choose_activity(message):
    try:
        act_id = int(message.text.split(".")[0])
    except:
        bot.send_message(message.chat.id, "Ошибка выбора.")
        return

    activity = session.query(Activity).get(act_id)
    if not activity:
        bot.send_message(message.chat.id, "Такой активности нет.")
        return

    bot.send_message(message.chat.id, "Отправьте фото или видео выполнения.")
    bot.register_next_step_handler(message, save_proof, activity)


def save_proof(message, activity):
    user = get_or_create_user(message)

    if message.content_type not in ["photo", "video"]:
        bot.send_message(message.chat.id, "Прикрепите фото или видео.")
        return

    file_id = (
        message.photo[-1].file_id
        if message.content_type == "photo"
        else message.video.file_id
    )

    sub = Submission(
        user_id=user.id,
        activity_id=activity.id,
        proof_type=message.content_type,
        proof_file=file_id,
        status="На проверке",
    )
    session.add(sub)
    session.commit()

    bot.send_message(message.chat.id, "Отправлено на проверку!")
    bot.send_message(
        ADMIN_ID,
        f"📥 Новое выполнение!\n"
        f"ID проверки: {sub.id}\n"
        f"Пользователь: @{user.username}\n"
        f"Активность: {activity.title}",
    )


@bot.message_handler(func=lambda m: m.text == "⬅ В главное меню")
def back_to_main(message):
    if is_admin(message):
        bot.send_message(message.chat.id, "Главное меню (админ)", reply_markup=admin_menu())
    else:
        bot.send_message(message.chat.id, "Главное меню", reply_markup=main_menu())


@bot.message_handler(func=lambda m: m.text == "➕ Добавить активность")
def add_activity(message):
    if not is_admin(message):
        return
    msg = bot.send_message(message.chat.id, "Введите название активности:")
    bot.register_next_step_handler(msg, add_activity_cost)


def add_activity_cost(message):
    title = message.text
    msg = bot.send_message(message.chat.id, "Введите стоимость:")
    bot.register_next_step_handler(msg, add_activity_description, title)


def add_activity_description(message, title):
    try:
        cost = int(message.text)
    except:
        bot.send_message(message.chat.id, "Стоимость должна быть числом.")
        return

    msg = bot.send_message(message.chat.id, "Введите описание:")
    bot.register_next_step_handler(msg, add_activity_multi, title, cost)


def add_activity_multi(message, title, cost):
    desc = message.text
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Да", "Нет")
    msg = bot.send_message(message.chat.id, "Многократное выполнение?", reply_markup=kb)
    bot.register_next_step_handler(msg, save_activity, title, cost, desc)


def save_activity(message, title, cost, desc):
    multi = message.text == "Да"
    a = Activity(title=title, cost=cost, description=desc, multiple=multi)
    session.add(a)
    session.commit()

    bot.send_message(message.chat.id, "Активность добавлена!", reply_markup=admin_menu())


@bot.message_handler(func=lambda m: m.text == "🗑 Удалить активность")
def delete_activity(message):
    if not is_admin(message):
        return
    msg = bot.send_message(message.chat.id, "Введите ID активности:")
    bot.register_next_step_handler(msg, delete_activity_confirm)


def delete_activity_confirm(message):
    try:
        act_id = int(message.text)
    except:
        bot.send_message(message.chat.id, "Неверный ID.")
        return

    a = session.query(Activity).get(act_id)
    if not a:
        bot.send_message(message.chat.id, "Активность не найдена.")
        return

    session.delete(a)
    session.commit()
    bot.send_message(message.chat.id, "Активность удалена.", reply_markup=admin_menu())


@bot.message_handler(func=lambda m: m.text == "📋 Все проверки")
def list_submissions(message):
    if not is_admin(message):
        return

    subs = session.query(Submission).filter_by(status="На проверке").all()
    if not subs:
        bot.send_message(message.chat.id, "Нет заявок.")
        return

    txt = "*Заявки:* \n\n"
    for s in subs:
        txt += f"ID {s.id} — @{s.user.username} — {s.activity.title}\n"

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✔ Принять", "❌ Отклонить")
    kb.add("⬅ В главное меню")

    bot.send_message(message.chat.id, txt, parse_mode="Markdown", reply_markup=kb)


@bot.message_handler(func=lambda m: m.text in ["✔ Принять", "❌ Отклонить"])
def admin_decision(message):
    if not is_admin(message):
        return

    status = "Принято" if message.text == "✔ Принять" else "Отклонено"

    msg = bot.send_message(message.chat.id, "Введите ID проверки:")
    bot.register_next_step_handler(msg, apply_status, status)


def apply_status(message, status):
    try:
        sub_id = int(message.text)
    except:
        bot.send_message(message.chat.id, "Ошибка ID.")
        return

    sub = session.query(Submission).get(sub_id)
    if not sub:
        bot.send_message(message.chat.id, "Заявка не найдена.")
        return

    sub.status = status
    session.commit()

    user = session.query(User).get(sub.user_id)
    activity = session.query(Activity).get(sub.activity_id)

    if status == "Принято":
        user.balance += activity.cost
        session.commit()
        bot.send_message(
            user.tg_id,
            f"🎉 Ваше выполнение '{activity.title}' принято! +{activity.cost} коинов."
        )
    else:
        bot.send_message(
            user.tg_id,
            f"❌ Ваше выполнение '{activity.title}' отклонено."
        )

    bot.send_message(ADMIN_ID, f"Статус обновлен: {status}")


@bot.message_handler(func=lambda m: m.text == "👥 Список пользователей")
def list_users(message):
    if not is_admin(message):
        return

    users = session.query(User).all()
    txt = "*Пользователи:*\n\n"
    for u in users:
        txt += f"@{u.username} — {u.balance} коинов\n"

    bot.send_message(message.chat.id, txt, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "💳 Управление балансом")
def manage_balance(message):
    msg = bot.send_message(message.chat.id, "Введите @username:")
    bot.register_next_step_handler(msg, balance_action)


def balance_action(message):
    username = message.text.replace("@", "")
    user = session.query(User).filter_by(username=username).first()

    if not user:
        bot.send_message(message.chat.id, "Пользователь не найден.")
        return

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Начислить", "➖ Списать")
    msg = bot.send_message(message.chat.id, "Выберите действие:", reply_markup=kb)
    bot.register_next_step_handler(msg, balance_apply, user)


def balance_apply(message, user):
    action = message.text
    msg = bot.send_message(message.chat.id, "Введите сумму:")
    bot.register_next_step_handler(msg, balance_final, user, action)


def balance_final(message, user, action):
    try:
        amount = int(message.text)
    except:
        bot.send_message(message.chat.id, "Сумма должна быть числом.")
        return

    if action == "➕ Начислить":
        user.balance += amount
    else:
        user.balance -= amount

    session.commit()

    bot.send_message(message.chat.id, "Баланс обновлен.")
    bot.send_message(user.tg_id, f"Ваш новый баланс: {user.balance} коинов.")


@bot.message_handler(func=lambda m: m.text == "🔄 Обнулить все балансы")
def reset_all_balances(message):
    if not is_admin(message):
        return

    for u in session.query(User).all():
        u.balance = 0
    session.commit()

    bot.send_message(message.chat.id, "Все балансы обнулены!")

@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if not is_admin(message):
        return
    bot.send_message(message.chat.id, "Админ-панель:", reply_markup=admin_menu())


# ----- /add_activity -----
@bot.message_handler(commands=["add_activity"])
def cmd_add_activity(message):
    if not is_admin(message):
        return
    msg = bot.send_message(message.chat.id, "Введите название активности:")
    bot.register_next_step_handler(msg, add_activity_cost)


# ----- /del_activity -----
@bot.message_handler(commands=["del_activity"])
def cmd_del_activity(message):
    if not is_admin(message):
        return
    msg = bot.send_message(message.chat.id, "Введите ID активности для удаления:")
    bot.register_next_step_handler(msg, delete_activity_confirm)


# ----- /users -----
@bot.message_handler(commands=["users"])
def cmd_users(message):
    if not is_admin(message):
        return
    return list_users(message)


# ----- /activities -----
@bot.message_handler(commands=["activities"])
def cmd_activities(message):
    return show_activities(message)


# ----- /submissions -----
@bot.message_handler(commands=["submissions"])
def cmd_submissions(message):
    if not is_admin(message):
        return
    return list_submissions(message)


# ----- /approve -----
@bot.message_handler(commands=["approve"])
def cmd_approve(message):
    if not is_admin(message):
        return
    msg = bot.send_message(message.chat.id, "Введите ID заявки для принятия:")
    bot.register_next_step_handler(msg, lambda m: apply_status(m, "Принято"))


# ----- /reject -----
@bot.message_handler(commands=["reject"])
def cmd_reject(message):
    if not is_admin(message):
        return
    msg = bot.send_message(message.chat.id, "Введите ID заявки для отклонения:")
    bot.register_next_step_handler(msg, lambda m: apply_status(m, "Отклонено"))


# ----- /give -----
@bot.message_handler(commands=["give"])
def cmd_give(message):
    if not is_admin(message):
        return
    msg = bot.send_message(message.chat.id, "Введите @username кому начислить коины:")
    bot.register_next_step_handler(msg, lambda m: balance_action_cmd(m, "give"))


# ----- /take -----
@bot.message_handler(commands=["take"])
def cmd_take(message):
    if not is_admin(message):
        return
    msg = bot.send_message(message.chat.id, "Введите @username у кого списать коины:")
    bot.register_next_step_handler(msg, lambda m: balance_action_cmd(m, "take"))


def balance_action_cmd(message, mode):
    username = message.text.replace("@", "")
    user = session.query(User).filter_by(username=username).first()

    if not user:
        bot.send_message(message.chat.id, "Пользователь не найден.")
        return

    msg = bot.send_message(message.chat.id, "Введите сумму:")
    bot.register_next_step_handler(msg, lambda m: balance_final_cmd(m, user, mode))


def balance_final_cmd(message, user, mode):
    try:
        amount = int(message.text)
    except:
        bot.send_message(message.chat.id, "Сумма должна быть числом.")
        return

    if mode == "give":
        user.balance += amount
    else:
        user.balance -= amount

    session.commit()

    bot.send_message(message.chat.id, "Баланс обновлён.")
    bot.send_message(user.tg_id, f"Ваш баланс теперь: {user.balance}")


# ----- /reset_balances -----
@bot.message_handler(commands=["reset_balances"])
def cmd_reset_balances(message):
    if not is_admin(message):
        return
    for u in session.query(User).all():
        u.balance = 0
    session.commit()
    bot.send_message(message.chat.id, "Все балансы обнулены!")


# ------------------ Старт бота ------------------
print("start app")
bot.infinity_polling()
