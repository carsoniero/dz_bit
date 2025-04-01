from passlib.handlers import bcrypt
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, TIMESTAMP, Boolean
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, nullable=False)
    hashed_password = Column(String, nullable=True)
    registered_at = Column(TIMESTAMP)
    is_active=Column(Boolean, default=True, nullable=False)
    is_superuser=Column(Boolean, default=True, nullable=False)
    is_verified=Column(Boolean, default=True, nullable=False)

    # Связь с таблицей Link (один пользователь -> много ссылок)
    links = relationship("Link", back_populates="owner")



    def verify_password(self, password):
        return bcrypt.verify(password, self.password_hash)

class Link(Base):
    __tablename__ = "link"
    id = Column(Integer, primary_key=True, index=True)
    short_code = Column(String, unique=True, index=True)
    original_url = Column(String)
    created_at = Column(DateTime)
    visits = Column(Integer, default=0)
    last_visited = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    owner_id = Column(Integer, ForeignKey("user.id"), nullable=True)

    # Обратная связь с пользователем
    owner = relationship("User", back_populates="links")



