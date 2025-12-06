from config import ADMIN_ID


def is_admin(message):
    return str(message.from_user.id) in ADMIN_ID.split(",")
