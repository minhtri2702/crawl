import subprocess
from db.session import SessionLocal
from models.manga import Manga
from models.chapter import Chapter
from sqlalchemy import func

NUM_WORKERS = 10

db = SessionLocal()

# Lấy 10 manga chưa crawl, sắp xếp theo số chapter giảm dần
mangas = (
    db.query(Manga, func.count(Chapter.id).label("chap_count"))
    .outerjoin(Chapter, Chapter.manga_id == Manga.id)
    .filter(Manga.min_chapter_crawled == 0)
    .group_by(Manga.id)
    .order_by(func.count(Chapter.id).desc())
    .limit(NUM_WORKERS)
    .all()
)

db.close()

if not mangas:
    print("Không còn manga nào để crawl!")
    exit(0)

print(f"Mở {len(mangas)} terminal, ưu tiên truyện nhiều chap nhất:")
for m, chap_count in mangas:
    print(f"  STT {m.stt}: {m.title} ({chap_count} chapters)")

for m, chap_count in mangas:
    cmd = f'start "STT {m.stt}" cmd /k "python main.py --mode chapters --manga-stt {m.stt} --chapters 10 && exit"'
    subprocess.call(cmd, shell=True)
