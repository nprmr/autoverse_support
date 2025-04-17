import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

def get_sheet():
    gspread_key = json.loads(os.environ.get("GSPREAD_JSON"))
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(gspread_key, scope)
    client = gspread.authorize(creds)
    sheet = client.open("AutoVerse Support Tickets").sheet1
    return sheet

def append_ticket(user_id, username, message, timestamp):
    sheet = get_sheet()
    sheet.append_row([str(user_id), username, message, timestamp, "новое"])
    return len(sheet.get_all_values())  # Возвращаем номер строки новой записи

def update_status(row_index, new_status):
    sheet = get_sheet()
    sheet.update_cell(row_index, 5, new_status)  # Колонка "Статус" = 5
