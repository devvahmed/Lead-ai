import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

# Database path (anchored to absolute backend folder)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_RAW_DB_NAME = os.getenv("DATABASE_FILE", "wtechx_ai.db")
DEFAULT_DB_FILE = _RAW_DB_NAME if os.path.isabs(_RAW_DB_NAME) else os.path.join(_BASE_DIR, _RAW_DB_NAME)
DB_PATH = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_FILE}")

engine = create_engine(
    DB_PATH,
    connect_args={"check_same_thread": False} if DB_PATH.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    website = Column(String(255), nullable=True)
    industry = Column(String(255), nullable=True)
    services = Column(Text, nullable=True)
    target_customers = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    logo_path = Column(String(512), nullable=True)
    ai_enriched_profile = Column(Text, nullable=True)
    smtp_email = Column(String(255), nullable=True)
    smtp_password = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

def init_auth_db():
    """Create companies table if it does not exist and ensure columns exist."""
    Base.metadata.create_all(bind=engine)
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            try:
                conn.execute(text("ALTER TABLE companies ADD COLUMN smtp_email TEXT"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE companies ADD COLUMN smtp_password TEXT"))
                conn.commit()
            except Exception:
                pass
    except Exception as e:
        print("[init_auth_db warning]:", e)

    # Ensure default company profiles exist so authentication/demo accounts always resolve
    try:
        db = SessionLocal()
        from auth_utils import hash_password

        # Seed WTechX
        wtechx = db.query(Company).filter(Company.name.ilike("wtechx")).first()
        if not wtechx:
            default_company = Company(
                id=1,
                name="WTechX",
                email="admin@wtechx.com",
                hashed_password=hash_password("admin123"),
                website="https://wtechx.com",
                industry="Robotics & AI Automation",
                services="AI, Robotics, and Computer Vision solutions provider",
                target_customers="Industrial and commercial enterprises seeking automation",
                description="Provider of intelligent automated solutions and robotic automation pipelines."
            )
            db.add(default_company)
            db.commit()
            print("[init_auth_db] Seeded default company profile (ID=1: WTechX)")

        db.close()
    except Exception as e:
        print("[init_auth_db seed warning]:", e)

def get_auth_db():
    """Dependency for obtaining DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
