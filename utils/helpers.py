import traceback

from database.db import db, Session
from database.models import User
import logging


logger = logging.getLogger(__name__)

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
