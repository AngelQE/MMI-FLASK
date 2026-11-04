import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# --- Opción A (por defecto): SQLite, un archivo junto al proyecto. No requiere instalar nada. ---
#RUTA_SQLITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mmi.db")
#DATABASE_URL = f"sqlite:///{RUTA_SQLITE}"

# --- Opción B: MySQL (XAMPP / phpMyAdmin). Crea una base vacía llamada mi_mundo_infantil, ---
# --- descomenta la línea de abajo y pon tu usuario/clave. Las tablas se crean solas.      ---
DATABASE_URL = "mysql+mysqlconnector://root:@localhost:3307/mi_mundo_infantil?charset=utf8mb4"

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session():
    return SessionLocal()
