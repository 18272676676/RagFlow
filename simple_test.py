import sys
from pathlib import Path

project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

print("Step 1: Import settings")
from RagFlow.config.settings import settings
print(f"OK: {settings.DATABASE_URL[:50]}...")

print("Step 2: Import database")
from RagFlow.core.database import engine
print(f"OK: {engine.url.database}")

print("Step 3: Test connection")
try:
    connection = engine.connect()
    print("OK: Connected to database")
    connection.close()
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("Step 4: Import models")
from RagFlow.models.db_models import Document, Chunk, QALog
print("OK: Models imported")

print("Step 5: Create tables")
try:
    from RagFlow.models.db_models import Base
    Base.metadata.create_all(bind=engine)
    print("OK: Tables created")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("Done!")
