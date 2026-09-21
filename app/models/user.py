from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    security_question = db.Column(db.String(200))
    security_answer_hash = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def set_security_answer(self, question: str, answer: str) -> None:
        self.security_question = question
        self.security_answer_hash = generate_password_hash(_normalize_answer(answer))

    def check_security_answer(self, answer: str) -> bool:
        if not self.security_answer_hash:
            return False
        return check_password_hash(self.security_answer_hash, _normalize_answer(answer))


def _normalize_answer(answer: str) -> str:
    return answer.strip().lower()
