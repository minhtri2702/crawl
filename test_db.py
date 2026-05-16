import sys
from sqlalchemy import text

print("Starting...", flush=True)

try:
    from db.session import SessionLocal
    print("Imported SessionLocal", flush=True)
    
    db = SessionLocal()
    print("Session created", flush=True)
    
    # Check manga count
    result = db.execute(text("SELECT COUNT(*) FROM manga"))
    count = result.scalar()
    print(f"Manga count: {count}", flush=True)
    
    # Check max stt
    result = db.execute(text("SELECT MAX(stt) FROM manga"))
    max_stt = result.scalar()
    print(f"Max STT: {max_stt}", flush=True)
    
    # Check for manga with stt=1
    result = db.execute(text("SELECT id, stt, title FROM manga WHERE stt = 1"))
    row = result.first()
    if row:
        print(f"Manga STT=1: ID={row[0]}, Title={row[2]}", flush=True)
    else:
        print("No manga with STT=1", flush=True)
    
    db.commit()
    print("Committed", flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)
    try:
        db.rollback()
    except:
        pass
finally:
    try:
        db.close()
    except:
        pass
    print("Done", flush=True)
