from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship, declarative_base


Base = declarative_base()

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
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User")
    activity = relationship("Activity")


class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    text = Column(Text)
    answer = Column(Text, nullable=True)
    status = Column(String, default="Новый")
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User")


class Poll(Base):
    __tablename__ = "polls"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    question = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
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
    created_at = Column(DateTime, default=datetime.now)

    poll = relationship("Poll")
    option = relationship("PollOption")
    user = relationship("User")
    