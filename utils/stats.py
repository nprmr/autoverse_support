import json
import os
from collections import Counter
from datetime import datetime
from utils.sheets import get_sheet

def generate_daily_report():
    sheet = get_sheet()
    data = sheet.get_all_values()[1:]  # пропускаем заголовки

    today = datetime.now().strftime("%Y-%m-%d")
    today_rows = [row for row in data if row[3].startswith(today)]

    total = len(today_rows)
    statuses = Counter(row[4].strip().lower() for row in today_rows if len(row) > 4)
    users = Counter(row[1].strip() if row[1].strip() else "без имени" for row in today_rows)

    report = [f"📊 Отчёт за {today}:", f"
Всего обращений: {total}", "
Статусы:"]
    for status, count in statuses.items():
        emoji = {
            "новое": "🟢",
            "в работу": "🛠",
            "готово": "✅",
            "отклонено": "❌"
        }.get(status, "📌")
        report.append(f"{emoji} {status}: {count}")

    report.append("
Топ авторы:")
    for i, (user, count) in enumerate(users.most_common(3), 1):
        report.append(f"{i}. {user} — {count}")

    return "\n".join(report)
