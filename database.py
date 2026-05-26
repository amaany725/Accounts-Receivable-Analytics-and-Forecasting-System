from sqlalchemy import create_engine
# =========================================
# DATABASE CONFIG
# =========================================
DB_USER = 'postgres'
DB_PASSWORD = 'Project2026'
DB_HOST = 'localhost'
DB_PORT = '5433'
DB_NAME = 'invoice_prediction'

DATABASE_URL = (

    f'postgresql://{DB_USER}:{DB_PASSWORD}'
    f'@{DB_HOST}:{DB_PORT}/{DB_NAME}'

)

# =========================================
# CREATE ENGINE
# =========================================
engine = create_engine(
    DATABASE_URL
)

