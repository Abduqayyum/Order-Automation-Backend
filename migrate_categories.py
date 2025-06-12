import os
import sys
import logging
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from database import DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def connect_to_postgres():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT,
            database="postgres"  
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to PostgreSQL: {e}")
        sys.exit(1)

def check_database_exists():
    conn = connect_to_postgres()
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{DB_NAME}'")
        exists = cursor.fetchone()
        
        if not exists:
            logger.info(f"Creating database '{DB_NAME}'...")
            cursor.execute(f"CREATE DATABASE {DB_NAME}")
            logger.info("Database created successfully!")
        else:
            logger.info(f"Database '{DB_NAME}' already exists.")
    except Exception as e:
        logger.error(f"Error checking/creating database: {e}")
    finally:
        cursor.close()
        conn.close()

def get_db_engine():
    return create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

def check_table_exists(engine, table_name):
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()

def create_categories_table():
    engine = get_db_engine()
    
    if check_table_exists(engine, "categories"):
        logger.info("Table 'categories' already exists.")
        return
    
    logger.info("Creating 'categories' table...")
    
    try:
        with engine.connect() as connection:
            connection.execute(text("""
                CREATE TABLE categories (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    description VARCHAR,
                    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            connection.execute(text("CREATE INDEX idx_categories_name ON categories (name)"))
            connection.execute(text("CREATE INDEX idx_categories_organization_id ON categories (organization_id)"))
            
            connection.commit()
            logger.info("Table 'categories' created successfully!")
    except SQLAlchemyError as e:
        logger.error(f"Error creating categories table: {e}")

def update_products_table():
    engine = get_db_engine()
    
    logger.info("Checking if product table needs updating...")
    
    try:
        with engine.connect() as connection:
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns('products')]
            
            if 'size' not in columns:
                logger.info("Adding 'size' column to products table...")
                connection.execute(text("ALTER TABLE products ADD COLUMN size VARCHAR"))
                logger.info("Added 'size' column successfully!")
            else:
                logger.info("Column 'size' already exists in products table.")
                
            if 'category_id' not in columns:
                logger.info("Adding 'category_id' column to products table...")
                connection.execute(text("""
                    ALTER TABLE products 
                    ADD COLUMN category_id INTEGER,
                    ADD CONSTRAINT fk_products_category 
                    FOREIGN KEY (category_id) 
                    REFERENCES categories(id) ON DELETE SET NULL
                """))
                logger.info("Added 'category_id' column successfully!")
            else:
                logger.info("Column 'category_id' already exists in products table.")
                
            connection.commit()
    except SQLAlchemyError as e:
        logger.error(f"Error updating products table: {e}")

def run_migration():
    logger.info("Starting database migration for categories...")
    
    check_database_exists()
    create_categories_table()
    update_products_table()
    
    logger.info("Migration completed successfully!")

if __name__ == "__main__":
    run_migration()
