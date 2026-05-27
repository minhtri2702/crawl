import subprocess
import time
import os
import logging
from db.session import SessionLocal
from models.manga import Manga
from models.chapter import Chapter
from sqlalchemy import func
from sqlalchemy.exc import OperationalError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

NUM_WORKERS = 9  # Số terminal tối đa chạy cùng lúc
MAX_RETRIES = 2  # Số lần retry khi mất kết nối DB
RETRY_DELAY = 2  # Giây chờ giữa các lần retry
BAT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_bat")

def get_next_batch(limit=NUM_WORKERS):
    """Lấy danh sách manga chưa crawl và đánh dấu đang crawl (min_chapter_crawled = -1)"""
    for attempt in range(MAX_RETRIES):
        try:
            db = SessionLocal()
            mangas = (
                db.query(Manga, func.count(Chapter.chapter_number).label("chap_count"))
                .join(Chapter, Chapter.manga_id == Manga.id)
                .filter(Manga.min_chapter_crawled == 0)
                .group_by(Manga.id)
                .order_by(func.count(Chapter.chapter_number).desc())
                .limit(limit)
                .all()
            )
            
            if not mangas:
                db.close()
                return []
            
            # Lưu thông tin cần thiết trước khi đóng session
            result = [(m.stt, m.title, chap_count) for m, chap_count in mangas]
            
            # Đánh dấu đang crawl
            manga_ids = [m.id for m, _ in mangas]
            db.query(Manga).filter(Manga.id.in_(manga_ids)).update(
                {Manga.min_chapter_crawled: -1},
                synchronize_session=False,
            )
            db.commit()
            db.close()
            return result
            
        except OperationalError as e:
            logger.error(f"Lỗi kết nối DB (lần {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                logger.info(f"Thử lại sau {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Đã hết số lần retry, bỏ qua.")
                return []

def start_terminal(stt, title, chap_count):
    """
    Tạo file .bat tạm và chạy nó.
    File .bat sẽ chạy python main.py và ghi PID vào file .pid
    """
    os.makedirs(BAT_DIR, exist_ok=True)
    
    bat_file = os.path.join(BAT_DIR, f"stt_{stt}.bat")
    pid_file = os.path.join(BAT_DIR, f"stt_{stt}.pid")
    
    # Xóa pid file cũ nếu có
    if os.path.exists(pid_file):
        os.remove(pid_file)
    
    # Tạo file .bat
    bat_content = f"""@echo off
cd /d "{os.path.dirname(os.path.abspath(__file__))}"
echo %~1 > "{pid_file}"
python main.py --mode chapters --manga-stt {stt} --chapters 3883
del "{pid_file}"
"""
    with open(bat_file, "w", encoding="utf-8") as f:
        f.write(bat_content)
    
    # Mở terminal mới chạy file .bat
    cmd = f'start "STT {stt}" cmd /k "{bat_file}"'
    proc = subprocess.Popen(cmd, shell=True)
    print(f"  🚀 STT {stt}: {title} ({chap_count} chapters)")
    return proc, stt, pid_file

def is_process_running(pid):
    """Kiểm tra process có đang chạy không dựa vào PID"""
    try:
        # Windows: tasklist /FI "PID eq {pid}"
        result = subprocess.run(
            f'tasklist /FI "PID eq {pid}" /NH',
            shell=True, capture_output=True, text=True, timeout=5
        )
        # Nếu output có chứa PID thì process đang chạy
        return str(pid) in result.stdout
    except:
        return False

def get_pid_from_file(pid_file):
    """Đọc PID từ file .pid"""
    try:
        if os.path.exists(pid_file):
            with open(pid_file, "r") as f:
                pid_str = f.read().strip()
                if pid_str:
                    return int(pid_str)
    except:
        pass
    return None

# === MAIN ===
print("📚 Bắt đầu crawl tự động...")
print(f"⚡ Tối đa {NUM_WORKERS} terminal cùng lúc\n")

# Mở batch đầu tiên
active = {}  # {stt: {"title": ..., "pid_file": ..., "pid": ...}}
batch = get_next_batch()
for stt, title, chap_count in batch:
    proc, stt, pid_file = start_terminal(stt, title, chap_count)
    active[stt] = {"title": title, "pid_file": pid_file, "pid": None}
    time.sleep(3)

total_opened = len(batch)
print(f"\n📊 Đã mở {total_opened} terminal. Đang theo dõi...\n")

# Vòng lặp theo dõi: khi có terminal chạy xong → mở terminal mới
while active:
    done_stts = []
    
    for stt, info in active.items():
        # Thử đọc PID từ file
        if info["pid"] is None:
            info["pid"] = get_pid_from_file(info["pid_file"])
        
        # Kiểm tra process
        if info["pid"] is not None:
            if not is_process_running(info["pid"]):
                done_stts.append(stt)
        else:
            # Chưa có PID, kiểm tra file pid có tồn tại không
            # Nếu file pid không tồn tại và cũng không có pid => process đã chạy xong
            if not os.path.exists(info["pid_file"]):
                done_stts.append(stt)
    
    for stt in done_stts:
        info = active.pop(stt)
        print(f"  ✅ STT {stt}: {info['title']} đã xong!")
        
        # Mở terminal mới cho manga tiếp theo
        next_batch = get_next_batch(limit=1)
        if next_batch:
            stt_new, title_new, chap_count_new = next_batch[0]
            proc_new, _, _ = start_terminal(stt_new, title_new, chap_count_new)
            active[stt_new] = {"title": title_new, "pid_file": os.path.join(BAT_DIR, f"stt_{stt_new}.pid"), "pid": None}
            total_opened += 1
            time.sleep(3)
    
    # Nếu còn process đang chạy, đợi 2s rồi kiểm tra lại
    if active:
        time.sleep(2)

print(f"\n✅ HOÀN TẤT! Đã crawl tổng cộng {total_opened} manga.")
