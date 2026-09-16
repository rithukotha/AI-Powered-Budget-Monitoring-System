# create_db.py
import os
import sys
from datetime import datetime
from werkzeug.security import generate_password_hash

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

# Create base
Base = declarative_base()

# Define User model
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(200), nullable=False)
    monthly_income = Column(Float, default=0)
    monthly_budget = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class Expense(Base):
    __tablename__ = 'expenses'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(50))
    description = Column(String(200))
    date = Column(DateTime, default=datetime.utcnow)
    receipt_image = Column(String(200))

class CategoryBudget(Base):
    __tablename__ = 'category_budgets'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    category = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)

def setup_database():
    # Delete existing database
    db_file = 'budget.db'
    if os.path.exists(db_file):
        print(f"Removing old database: {db_file}")
        os.remove(db_file)
    
    # Create engine and tables
    engine = create_engine(f'sqlite:///{db_file}')
    Base.metadata.create_all(engine)
    
    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Create test users with pbkdf2:sha256 method
    try:
        # Test User 1
        test_user1 = User(
            name='Test User',
            email='test@example.com',
            password=generate_password_hash('test123', method='pbkdf2:sha256'),
            monthly_income=50000,
            monthly_budget=40000
        )
        session.add(test_user1)
        
        # Test User 2
        test_user2 = User(
            name='Demo User',
            email='demo@example.com',
            password=generate_password_hash('demo123', method='pbkdf2:sha256'),
            monthly_income=80000,
            monthly_budget=60000
        )
        session.add(test_user2)
        
        session.commit()
        
        print("=" * 50)
        print("Database setup complete!")
        print("=" * 50)
        print("Test users created:")
        print("1. Email: test@example.com | Password: test123")
        print("2. Email: demo@example.com | Password: demo123")
        print("=" * 50)
        
    except Exception as e:
        print(f"Error: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == '__main__':
    setup_database()