from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from database.models import Base
from config import DB_PATH


engine = create_engine(DB_PATH, echo=False)
SessionFactory = sessionmaker(bind=engine)
Session = scoped_session(SessionFactory)

def db():
    return Session()

def init_db():
    Base.metadata.create_all(engine)
