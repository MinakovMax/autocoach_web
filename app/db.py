from dotenv import load_dotenv
load_dotenv()
import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, func
from sqlalchemy.orm import Session
from datetime import datetime

# Подключение к базе данных через переменную окружения
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/autocoach")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False)
    transcript = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    transcript = Column(Text, nullable=False)
    type = Column(String, nullable=False) 
    recommendation = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

def init_db():
    Base.metadata.create_all(bind=engine)



def save_recommendation(text: str, transcript: str, rec_type: str):
    db: Session = SessionLocal()
    try:
        recommendation = Recommendation(
            transcript=transcript,
            recommendation=text,
            type=rec_type,
            created_at=datetime.utcnow()
        )
        db.add(recommendation)
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()