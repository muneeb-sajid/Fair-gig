# seed_db.py - Auto-generates 200 workers in Lahore for Tayyab's frontend
# Fixed version - no syntax errors

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from main import Base, Worker, Earning
from passlib.context import CryptContext
from faker import Faker
import random
from datetime import datetime, timedelta

fake = Faker()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DATABASE_URL = "sqlite:///./fairgig.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# Platforms (matching Tayyab's frontend)
PLATFORMS = ["Uber", "Foodpanda", "Careem", "Bykea", "Indrive"]

# Cities (70% Lahore for median calculation)
CITIES = ["Lahore", "Lahore", "Lahore", "Lahore", "Lahore", "Lahore", "Lahore", "Karachi", "Islamabad", "Rawalpindi"]

def generate_worker(index):
    """Generate a single worker"""
    city = random.choice(CITIES)
    platform = random.choice(PLATFORMS)
    
    # Generate a date within last 6 months
    six_months_ago = datetime.now() - timedelta(days=180)
    created_at = fake.date_time_between(start_date=six_months_ago, end_date='now')
    
    return Worker(
        name=fake.name(),
        email=f"worker_{index}_{fake.email()}",
        password=pwd_context.hash("password123"),
        phone=fake.phone_number(),
        city=city,
        platform=platform,
        role="worker",
        total_earnings=0,
        is_active=True,
        created_at=created_at
    )

def generate_earnings(worker, num_shifts):
    """Generate earnings/shifts for a worker (for Tayyab's dashboard)"""
    earnings = []
    dates = []
    
    # Generate random dates within last 90 days
    for _ in range(num_shifts):
        ninety_days_ago = datetime.now() - timedelta(days=90)
        date = fake.date_between(start_date=ninety_days_ago, end_date='today')
        dates.append(date)
    
    dates.sort()  # Chronological order
    
    for i, date in enumerate(dates):
        # Random earnings between Rs. 500 and Rs. 8000
        net_amount = random.randint(500, 8000)
        
        # Calculate gross (net + deductions, typically 10-25% more)
        deductions = random.randint(50, 300)
        gross_amount = net_amount + deductions
        
        # Hours worked (4-12 hours)
        hours = random.randint(4, 12)
        
        earning = Earning(
            worker_id=worker.id,
            amount=net_amount,
            platform=worker.platform,
            date=date.isoformat(),
            hours=hours,
            gross=gross_amount,
            deductions=deductions
        )
        earnings.append(earning)
        
        # Update worker's total earnings
        worker.total_earnings += net_amount
    
    return earnings

def seed_database():
    """Main seeding function - Creates 200 workers with earnings"""
    print("=" * 50)
    print("🌱 SEEDING DATABASE FOR TAYYAB'S FRONTEND")
    print("=" * 50)
    
    db = SessionLocal()
    
    # Clear existing data
    print("\n🗑️ Clearing existing data...")
    db.query(Earning).delete()
    db.query(Worker).delete()
    db.commit()
    
    # Create 200 workers
    print("\n👥 Creating 200 workers...")
    workers = []
    for i in range(200):
        worker = generate_worker(i)
        workers.append(worker)
    
    db.add_all(workers)
    db.commit()
    print(f"   ✅ Created {len(workers)} workers")
    
    # Generate earnings for each worker (5-25 shifts per worker)
    print("\n💰 Generating earnings records...")
    total_earnings = 0
    
    for worker in workers:
        # Each worker has between 5 and 25 shifts
        num_shifts = random.randint(5, 25)
        earnings = generate_earnings(worker, num_shifts)
        db.add_all(earnings)
        total_earnings += len(earnings)
    
    db.commit()
    print(f"   ✅ Added {total_earnings} earnings records")
    
    # ==========================================
    # STATISTICS FOR TAYYAB'S FRONTEND
    # ==========================================
    print("\n" + "=" * 50)
    print("📊 DATABASE STATISTICS")
    print("=" * 50)
    
    # Workers by city (for city-median calculation)
    lahore_workers = db.query(Worker).filter(Worker.city == "Lahore").count()
    karachi_workers = db.query(Worker).filter(Worker.city == "Karachi").count()
    islamabad_workers = db.query(Worker).filter(Worker.city == "Islamabad").count()
    
    print(f"\n📍 Workers by City:")
    print(f"   Lahore: {lahore_workers} workers")
    print(f"   Karachi: {karachi_workers} workers")
    print(f"   Islamabad: {islamabad_workers} workers")
    
    # Workers by platform
    print(f"\n🚗 Workers by Platform:")
    for platform in PLATFORMS:
        count = db.query(Worker).filter(Worker.platform == platform).count()
        print(f"   {platform}: {count} workers")
    
    # Earnings statistics for Lahore (for city-median API)
    lahore_worker_ids = [w.id for w in db.query(Worker).filter(Worker.city == "Lahore").all()]
    if lahore_worker_ids:
        lahore_earnings = db.query(Earning).filter(Earning.worker_id.in_(lahore_worker_ids)).all()
        lahore_amounts = [e.amount for e in lahore_earnings]
        lahore_amounts.sort()
        lahore_median = lahore_amounts[len(lahore_amounts)//2] if lahore_amounts else 0
        
        print(f"\n📈 Lahore Earnings Statistics:")
        print(f"   Total earnings records: {len(lahore_amounts)}")
        print(f"   City Median: Rs. {lahore_median:,.2f}")
        if lahore_amounts:
            print(f"   Min Earnings: Rs. {min(lahore_amounts):,.2f}")
            print(f"   Max Earnings: Rs. {max(lahore_amounts):,.2f}")
            print(f"   Average Earnings: Rs. {sum(lahore_amounts)/len(lahore_amounts):,.2f}")
    
    # Total summary
    total_earnings_sum = db.query(Earning).count()
    total_amount_sum = db.query(func.sum(Earning.amount)).scalar() or 0
    
    print(f"\n💰 Overall Summary:")
    print(f"   Total Workers: {len(workers)}")
    print(f"   Total Shifts/Earnings: {total_earnings_sum}")
    print(f"   Total Earnings Amount: Rs. {total_amount_sum:,.2f}")
    if total_earnings_sum > 0:
        print(f"   Average per Shift: Rs. {total_amount_sum/total_earnings_sum:,.2f}")
    
    # ==========================================
    # SAMPLE DATA FOR TAYYAB TO TEST
    # ==========================================
    print("\n" + "=" * 50)
    print("🎯 SAMPLE DATA FOR TAYYAB'S FRONTEND")
    print("=" * 50)
    
    # Get a sample worker for Tayyab to test
    sample_worker = workers[0]
    sample_earnings = db.query(Earning).filter(Earning.worker_id == sample_worker.id).limit(5).all()
    
    print(f"\n📋 Sample Worker (for testing):")
    print(f"   ID: {sample_worker.id}")
    print(f"   Name: {sample_worker.name}")
    print(f"   Email: {sample_worker.email}")
    print(f"   Password: password123")
    print(f"   Platform: {sample_worker.platform}")
    print(f"   City: {sample_worker.city}")
    
    print(f"\n💰 Sample Earnings (last 5 shifts):")
    for e in sample_earnings[:5]:
        print(f"   {e.date}: Rs. {e.amount:,.2f} (Hours: {e.hours}, Gross: Rs. {e.gross:,.2f}, Deductions: Rs. {e.deductions:,.2f})")
    
    # ==========================================
    # API ENDPOINTS FOR TAYYAB TO USE
    # ==========================================
    print("\n" + "=" * 50)
    print("🔗 API ENDPOINTS FOR TAYYAB'S FRONTEND")
    print("=" * 50)
    print("\nWorker Dashboard APIs:")
    print("   POST   http://localhost:8000/api/auth/login")
    print("   POST   http://localhost:8000/api/auth/register")
    print("   GET    http://localhost:8000/api/earnings/{user_id}")
    print("   GET    http://localhost:8000/api/earnings/city-median?city=Lahore")
    print("   POST   http://localhost:8000/api/earnings")
    print("   POST   http://localhost:3001/api/grievances")
    print("   GET    http://localhost:3001/api/grievances")
    
    print("\nAdvocate Dashboard APIs:")
    print("   GET    http://localhost:3001/api/analytics/complaints")
    print("   POST   http://localhost:8001/api/detect-anomaly")
    
    print("\n" + "=" * 50)
    print("🎉 SEEDING COMPLETE! READY FOR TAYYAB'S FRONTEND")
    print("=" * 50)
    
    db.close()

if __name__ == "__main__":
    seed_database()