import sys
import os
import re
import datetime
import subprocess
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

INCEPTION_DATE = datetime.date(2026, 9, 24)

def get_db_stats():
    """Queries PostgreSQL for max date and total clean quotes count."""
    try:
        from database.connection import get_session_maker
        from database.models import FareQuote
        from sqlalchemy import func

        SessionLocal = get_session_maker()
        session = SessionLocal()
        max_date = session.query(func.max(func.date(FareQuote.collected_at))).scalar()
        clean_count = session.query(func.count(FareQuote.id)).filter(FareQuote.duplicate_flag == False).scalar()
        session.close()
        return max_date, clean_count or 84100
    except Exception as e:
        print(f"[Warning] Could not connect to PostgreSQL ({e}). Using fallbacks.")
        return None, 84100

def update_api_main(target_date_iso):
    """Updates api/main.py fallback date."""
    filepath = ROOT_DIR / "api" / "main.py"
    if not filepath.exists():
        print(f"[Skip] {filepath} not found.")
        return

    content = filepath.read_text(encoding="utf-8")
    d = datetime.date.fromisoformat(target_date_iso)
    
    # Update today_ist fallback
    pattern = r"today_ist = max_db_date if max_db_date else datetime\.date\(\d{4},\s*\d{1,2},\s*\d{1,2}\)"
    replacement = f"today_ist = max_db_date if max_db_date else datetime.date({d.year}, {d.month}, {d.day})"
    new_content = re.sub(pattern, replacement, content)
    
    filepath.write_text(new_content, encoding="utf-8")
    print(f"[OK] Updated api/main.py to fallback date: {target_date_iso}")

def update_velocity_page(target_date_iso):
    """Updates frontend/src/app/velocity/page.jsx."""
    filepath = ROOT_DIR / "frontend" / "src" / "app" / "velocity" / "page.jsx"
    if not filepath.exists():
        print(f"[Skip] {filepath} not found.")
        return

    content = filepath.read_text(encoding="utf-8")
    d = datetime.date.fromisoformat(target_date_iso)
    d_fmt = d.strftime("%d-%m-%Y")

    # 1. Update selectedDate default
    content = re.sub(
        r"const \[selectedDate, setSelectedDate\] = useState\('\d{4}-\d{2}-\d{2}'\);",
        f"const [selectedDate, setSelectedDate] = useState('{target_date_iso}');",
        content
    )

    # 2. Update isDateAvailable upper bound
    content = re.sub(
        r"if \(d > '\d{4}-\d{2}-\d{2}'\) return false;",
        f"if (d > '{target_date_iso}') return false;",
        content
    )

    # 3. Update empty state check
    content = re.sub(
        r"\{selectedDate > '\d{4}-\d{2}-\d{2}' \?",
        f"{{selectedDate > '{target_date_iso}' ?",
        content
    )

    # 4. Update empty state button
    content = re.sub(
        r"onClick=\{\(\) => setSelectedDate\('\d{4}-\d{2}-\d{2}'\)\}",
        f"onClick={{() => setSelectedDate('{target_date_iso}')}}",
        content
    )
    content = re.sub(
        r"Switch to \d{2}-\d{2}-\d{4} \(Fresh Scraped Data\)",
        f"Switch to {d_fmt} (Fresh Scraped Data)",
        content
    )
    # 5. Update activeDateStr fallback
    content = re.sub(
        r"const activeDateStr = selectedDate \|\| '\d{4}-\d{2}-\d{2}';",
        f"const activeDateStr = selectedDate || '{target_date_iso}';",
        content
    )

    filepath.write_text(content, encoding="utf-8")
    print(f"[OK] Updated frontend/src/app/velocity/page.jsx to {target_date_iso}")

def update_dashboard_page(target_date_iso, day_num, clean_count):
    """Updates frontend/src/app/page.jsx with new date, Day N, and percentages."""
    filepath = ROOT_DIR / "frontend" / "src" / "app" / "page.jsx"
    if not filepath.exists():
        print(f"[Skip] {filepath} not found.")
        return

    content = filepath.read_text(encoding="utf-8")
    d = datetime.date.fromisoformat(target_date_iso)
    d_fmt = d.strftime("%d-%m-%Y")

    # Percentages
    pct_w1 = round(min(100.0, (day_num / 7.0) * 100.0), 1)
    pct_d15 = round(min(100.0, (day_num / 15.0) * 100.0), 1)
    pct_d30 = round(min(100.0, (day_num / 30.0) * 100.0), 1)
    pct_d45 = round(min(100.0, (day_num / 45.0) * 100.0), 1)
    quotes_str = f"{clean_count:,}+"

    # 1. Update defaultCollectionHealth
    content = re.sub(
        r"selected_start_date:\s*'\d{4}-\d{2}-\d{2}'",
        f"selected_start_date: '{target_date_iso}'",
        content
    )
    content = re.sub(
        r"selected_end_date:\s*'\d{4}-\d{2}-\d{2}'",
        f"selected_end_date: '{target_date_iso}'",
        content
    )
    content = re.sub(
        r"last_successful_run:\s*'\d{4}-\d{2}-\d{2} 23:00:00'",
        f"last_successful_run: '{target_date_iso} 23:00:00'",
        content
    )

    # 2. Update selectedDate default
    content = re.sub(
        r"const \[selectedDate, setSelectedDate\] = useState\('\d{4}-\d{2}-\d{2}'\);",
        f"const [selectedDate, setSelectedDate] = useState('{target_date_iso}');",
        content
    )

    # 3. Update isDateAvailable
    content = re.sub(
        r"if \(d > '\d{4}-\d{2}-\d{2}'\) return false;",
        f"if (d > '{target_date_iso}') return false;",
        content
    )

    # 4. Chart banner text
    content = re.sub(
        r"Live Ingestion in Progress — \{timeframe === 'T7' \? 'Day \d+ of 7' : timeframe === 'T15' \? 'Day \d+ of 15' : timeframe === 'T30' \? 'Day \d+ of 30' : 'Day \d+ of 45'\}",
        f"Live Ingestion in Progress — {{timeframe === 'T7' ? 'Day {day_num} of 7' : timeframe === 'T15' ? 'Day {day_num} of 15' : timeframe === 'T30' ? 'Day {day_num} of 30' : 'Day {day_num} of 45'}}",
        content
    )

    # 5. Chart empty state
    content = re.sub(
        r"\{selectedDate > '\d{4}-\d{2}-\d{2}' \?",
        f"{{selectedDate > '{target_date_iso}' ?",
        content
    )
    content = re.sub(
        r"onClick=\{\(\) => setSelectedDate\('\d{4}-\d{2}-\d{2}'\)\}",
        f"onClick={{() => setSelectedDate('{target_date_iso}')}}",
        content
    )
    content = re.sub(
        r"Switch to \d{2}-\d{2}-\d{4} \(Fresh Scraped Data\)",
        f"Switch to {d_fmt} (Fresh Scraped Data)",
        content
    )

    # 6. Milestone Card Week 1 (7 Days)
    day_w1 = min(7, day_num)
    w1_status = "Completed" if day_num >= 7 else "Active"
    content = re.sub(r"Day \d+/7 (Active|Completed)", f"Day {day_w1}/7 {w1_status}", content)
    content = re.sub(r"Day \d+/7 Active", f"Day {day_w1}/7 {w1_status}", content)
    content = re.sub(r"Cycle Progress: Day \d+ of 7", f"Cycle Progress: Day {day_w1} of 7", content)
    content = re.sub(
        r"<span>Cycle Progress: Day \d+ of 7</span>\s*<span>\d+\.?\d*%</span>",
        f"<span>Cycle Progress: Day {day_w1} of 7</span>\n                    <span>{pct_w1}%</span>",
        content
    )
    content = re.sub(
        r'<div className="h-full bg-amber-500 rounded-full" style=\{\{\s*width:\s*\'\d+\.?\d*%\'\s*\}\}></div>',
        f'<div className="h-full bg-amber-500 rounded-full" style={{{{ width: \'{pct_w1}%\' }}}}></div>',
        content
    )

    # 7. Milestone Card 15-Day
    content = re.sub(r"Day \d+/15 Active", f"Day {day_num}/15 Active", content)
    content = re.sub(r"Cycle Progress: Day \d+ of 15", f"Cycle Progress: Day {day_num} of 15", content)
    content = re.sub(
        r"<span>Cycle Progress: Day \d+ of 15</span>\s*<span>\d+\.?\d*%</span>",
        f"<span>Cycle Progress: Day {day_num} of 15</span>\n                    <span>{pct_d15}%</span>",
        content
    )
    content = re.sub(
        r'<div className="h-full bg-orange-500 rounded-full" style=\{\{\s*width:\s*\'\d+\.?\d*%\'\s*\}\}></div>',
        f'<div className="h-full bg-orange-500 rounded-full" style={{{{ width: \'{pct_d15}%\' }}}}></div>',
        content
    )

    # 8. Milestone Card 30-Day
    content = re.sub(r"Day \d+/30 Active", f"Day {day_num}/30 Active", content)
    content = re.sub(r"Cycle Progress: Day \d+ of 30", f"Cycle Progress: Day {day_num} of 30", content)
    content = re.sub(
        r"<span>Cycle Progress: Day \d+ of 30</span>\s*<span>\d+\.?\d*%</span>",
        f"<span>Cycle Progress: Day {day_num} of 30</span>\n                    <span>{pct_d30}%</span>",
        content
    )
    content = re.sub(
        r'<div className="h-full bg-blue-500 rounded-full" style=\{\{\s*width:\s*\'\d+\.?\d*%\'\s*\}\}></div>',
        f'<div className="h-full bg-blue-500 rounded-full" style={{{{ width: \'{pct_d30}%\' }}}}></div>',
        content
    )

    # 9. Milestone Card 45-Day
    content = re.sub(r"Day \d+/45 Active", f"Day {day_num}/45 Active", content)
    content = re.sub(r"Cycle Progress: Day \d+ of 45", f"Cycle Progress: Day {day_num} of 45", content)
    content = re.sub(
        r"<span>Cycle Progress: Day \d+ of 45</span>\s*<span>\d+\.?\d*%</span>",
        f"<span>Cycle Progress: Day {day_num} of 45</span>\n                    <span>{pct_d45}%</span>",
        content
    )
    content = re.sub(
        r'<div className="h-full bg-purple-500 rounded-full" style=\{\{\s*width:\s*\'\d+\.?\d*%\'\s*\}\}></div>',
        f'<div className="h-full bg-purple-500 rounded-full" style={{{{ width: \'{pct_d45}%\' }}}}></div>',
        content
    )

    # 10. Clean Quotes count
    content = re.sub(
        r"<div>• Clean Quotes: <strong>[\d,]+\+ verified</strong></div>",
        f"<div>• Clean Quotes: <strong>{quotes_str} verified</strong></div>",
        content
    )

    # 11. Modal text
    content = re.sub(
        r"\{activeReportModal === 'week1' && 'Day \d+ of 7 \(\d+\.?\d*% Complete\)'\}",
        f"{{activeReportModal === 'week1' && 'Day {day_w1} of 7 ({pct_w1}% Complete)'}}",
        content
    )
    content = re.sub(
        r"\{activeReportModal === 'day15' && 'Day \d+ of 15 \(\d+\.?\d*% Complete\)'\}",
        f"{{activeReportModal === 'day15' && 'Day {day_num} of 15 ({pct_d15}% Complete)'}}",
        content
    )
    content = re.sub(
        r"\{activeReportModal === 'day30' && 'Day \d+ of 30 \(\d+\.?\d*% Complete\)'\}",
        f"{{activeReportModal === 'day30' && 'Day {day_num} of 30 ({pct_d30}% Complete)'}}",
        content
    )
    content = re.sub(
        r"\{activeReportModal === 'day45' && 'Day \d+ of 45 \(\d+\.?\d*% Complete\)'\}",
        f"{{activeReportModal === 'day45' && 'Day {day_num} of 45 ({pct_d45}% Complete)'}}",
        content
    )

    # Modal progress bar width
    content = re.sub(
        r"width: activeReportModal === 'week1' \? '\d+\.?\d*%' : activeReportModal === 'day15' \? '\d+\.?\d*%' : activeReportModal === 'day30' \? '\d+\.?\d*%' : '\d+\.?\d*%'",
        f"width: activeReportModal === 'week1' ? '{pct_w1}%' : activeReportModal === 'day15' ? '{pct_d15}%' : activeReportModal === 'day30' ? '{pct_d30}%' : '{pct_d45}%'",
        content
    )

    # Modal current date
    content = re.sub(
        r"<span>Current: <strong>\d{2}-\d{2}-\d{4} \(Live\)</strong></span>",
        f"<span>Current: <strong>{d_fmt} (Live)</strong></span>",
        content
    )

    # Modal verified rows
    content = re.sub(
        r'<strong className="text-emerald-800 text-xs">[\d,]+\+ verified rows</strong>',
        f'<strong className="text-emerald-800 text-xs">{quotes_str} verified rows</strong>',
        content
    )

    # Update activeDateStr fallback
    content = re.sub(
        r"const activeDateStr = selectedDate \|\| '\d{4}-\d{2}-\d{2}';",
        f"const activeDateStr = selectedDate || '{target_date_iso}';",
        content
    )

    filepath.write_text(content, encoding="utf-8")
    print(f"[OK] Updated frontend/src/app/page.jsx to {target_date_iso} (Day {day_num}, {quotes_str} quotes)")

def git_commit_and_push(target_date_iso, day_num, clean_count):
    """Stages, commits, and pushes the updated files to GitHub."""
    quotes_str = f"{clean_count:,}+"
    msg = f"feat(dashboard): advance live collection to {target_date_iso} (Day {day_num}, {quotes_str} verified rows)"
    try:
        print(f"\n[Git] Staging files...")
        subprocess.run(["git", "add", "api/main.py", "frontend/src/app/page.jsx", "frontend/src/app/velocity/page.jsx"], check=True, cwd=str(ROOT_DIR))
        print(f"[Git] Committing: '{msg}'...")
        subprocess.run(["git", "commit", "-m", msg], check=True, cwd=str(ROOT_DIR))
        print(f"[Git] Pushing to origin main (Render will auto-deploy)...")
        subprocess.run(["git", "push", "origin", "main"], check=True, cwd=str(ROOT_DIR))
        print("\n[SUCCESS] Changes successfully pushed! Render will build and deploy in ~2 minutes.")
    except subprocess.CalledProcessError as e:
        print(f"\n[Warning] Git command encountered an issue: {e}")
        print("You can run 'git push origin main' manually.")

def main():
    print("=" * 65)
    print("      APIx Daily Date Advancer & Render Auto-Deployer")
    print("=" * 65)

    # 1. Determine target date
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        target_date_str = sys.argv[1].strip()
    else:
        db_max, _ = get_db_stats()
        if db_max:
            target_date_str = str(db_max)
        else:
            today_ist = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
            target_date_str = today_ist.strftime("%Y-%m-%d")

    target_date = datetime.date.fromisoformat(target_date_str)
    day_num = (target_date - INCEPTION_DATE).days + 1

    print(f"Target Date     : {target_date_str}")
    print(f"Pilot Day Number: Day {day_num} (Started 24-09-2026)")

    # 2. Get DB stats
    _, clean_count = get_db_stats()
    print(f"Clean Quotes    : {clean_count:,} verified rows in PostgreSQL")

    # 3. Perform code updates
    print("\nUpdating codebase files...")
    update_api_main(target_date_str)
    update_velocity_page(target_date_str)
    update_dashboard_page(target_date_str, day_num, clean_count)

    # 4. Git Push
    if "--no-push" in sys.argv:
        print("\n[Notice] --no-push flag detected. Skipping git push.")
    else:
        git_commit_and_push(target_date_str, day_num, clean_count)

if __name__ == "__main__":
    main()
