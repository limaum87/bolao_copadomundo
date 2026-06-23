import uuid
from datetime import datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


def generate_uid() -> str:
    return uuid.uuid4().hex


class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    uid = Column(String, unique=True, default=generate_uid, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    predictions = relationship("Prediction", back_populates="participant", cascade="all, delete-orphan")
    finals_prediction = relationship(
        "FinalsPrediction", back_populates="participant", cascade="all, delete-orphan", uselist=False
    )


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True)
    kickoff = Column(DateTime, nullable=False)
    team_a = Column(String, nullable=False)
    team_b = Column(String, nullable=False)
    score_a = Column(Integer, nullable=True)
    score_b = Column(Integer, nullable=True)
    # scheduled | live (placar parcial ao vivo) | finished (FT travado)
    status = Column(String, nullable=False, default="scheduled")

    predictions = relationship("Prediction", back_populates="game", cascade="all, delete-orphan")


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("participant_id", "game_id", name="uq_participant_game"),)

    id = Column(Integer, primary_key=True)
    participant_id = Column(Integer, ForeignKey("participants.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    goals_a = Column(Integer, nullable=False)
    goals_b = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    participant = relationship("Participant", back_populates="predictions")
    game = relationship("Game", back_populates="predictions")


class FinalsPrediction(Base):
    __tablename__ = "finals_predictions"
    __table_args__ = (UniqueConstraint("participant_id", name="uq_participant_finals"),)

    id = Column(Integer, primary_key=True)
    participant_id = Column(Integer, ForeignKey("participants.id"), nullable=False)
    champion = Column(String, nullable=False)
    runner_up = Column(String, nullable=False)
    third_place = Column(String, nullable=False)
    fourth_place = Column(String, nullable=False)

    participant = relationship("Participant", back_populates="finals_prediction")


class TournamentOutcome(Base):
    __tablename__ = "tournament_outcome"

    id = Column(Integer, primary_key=True, default=1)
    champion = Column(String, nullable=True)
    runner_up = Column(String, nullable=True)
    third_place = Column(String, nullable=True)
    fourth_place = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ScoringConfig(Base):
    __tablename__ = "scoring_config"

    id = Column(Integer, primary_key=True, default=1)
    exact_score = Column(Integer, nullable=False, default=10)
    correct_result = Column(Integer, nullable=False, default=5)
    partial_score = Column(Integer, nullable=False, default=2)
    champion = Column(Integer, nullable=False, default=50)
    runner_up = Column(Integer, nullable=False, default=15)
    third_place = Column(Integer, nullable=False, default=10)
    fourth_place = Column(Integer, nullable=False, default=10)
    finals_deadline = Column(DateTime, nullable=True)
    # Hora (0-23) do lembrete diário de palpites faltantes. Default 11h.
    daily_reminder_hour = Column(Integer, nullable=False, default=11)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PushSubscription(Base):
    """Inscrições Web Push por participante (uma por dispositivo/navegador)."""

    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True)
    participant_uid = Column(String, nullable=False, index=True)
    endpoint = Column(String, nullable=False, unique=True)
    p256dh = Column(String, nullable=True)
    auth_key = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotificationLog(Base):
    """Registro idempotente de notificações automáticas (evita duplicatas)."""

    __tablename__ = "notification_log"

    id = Column(Integer, primary_key=True)
    log_key = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RankingSnapshot(Base):
    """Snapshot diário do ranking: posição/pontos de cada participante num dado dia.

    Usado para calcular a variação de posição desde o dia anterior (↑/↓).
    Um snapshot por (snapshot_date, participant_id)."""

    __tablename__ = "ranking_snapshots"
    __table_args__ = (
        UniqueConstraint("snapshot_date", "participant_id", name="uq_snapshot_date_participant"),
    )

    id = Column(Integer, primary_key=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    participant_id = Column(Integer, ForeignKey("participants.id"), nullable=False)
    position = Column(Integer, nullable=False)
    points = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

