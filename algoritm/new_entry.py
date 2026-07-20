import re

def cells_in_insert(row, barcode, colors, link):
    parts = [row.get('P'), row.get('Q'), row.get('J'), row.get('K')]
    product_name = ' '.join(filter(None, parts))
    data_map = {
        'A': barcode,
        'B': product_name,
        'C': row.get('E', ''),
        'D': '',
        'E': '',
        'F': link
    }
    remaining_colors = colors.copy()
    data_map['G'] = remaining_colors.pop('C', '')
    data_map['H'] = remaining_colors.pop('M', '')
    data_map['I'] = remaining_colors.pop('Y', '')
    data_map['J'] = remaining_colors.pop('K', '')
    col_char = ord('K')
    for val in remaining_colors.values():
        data_map[chr(col_char)] = val
        col_char += 1
    max_col = max(data_map.keys())
    row_list = [data_map.get(chr(i), '') for i in range(ord('A'), ord(max_col) + 1)]

    return row_list


def add_row_to_sheet(service, id_sheet, row_list, sheet_name):
    range_name = f"{sheet_name}!A1"
    body = {'values': [row_list]}
    result = service.spreadsheets().values().append(
        spreadsheetId=id_sheet,
        range=range_name,
        valueInputOption='USER_ENTERED',
        body=body
    ).execute()

    updated_range = result['updates']['updatedRange']
    print(f"Строка добавлена в диапазон: {updated_range}")

    cell_part = updated_range.split('!')[1].split(':')[0]
    match = re.search(r'\d+', cell_part)
    row_index = int(match.group()) - 1

    spreadsheet = service.spreadsheets().get(spreadsheetId=id_sheet).execute()
    sheet_id = None
    for sheet in spreadsheet.get('sheets', []):
        if sheet['properties']['title'] == sheet_name:
            sheet_id = sheet['properties']['sheetId']
            break

    if sheet_id is None:
        print(f"Ошибка: Лист '{sheet_name}' не найден. Форматирование не применено.")
        return result

    requests = [
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row_index,
                    "endRowIndex": row_index + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 6
                },
                "cell": {
                    "userEnteredFormat": {
                        "borders": {
                            "top": {"style": "SOLID"},
                            "bottom": {"style": "SOLID"},
                            "left": {"style": "SOLID"},
                            "right": {"style": "SOLID"}
                        }
                    }
                },
                "fields": "userEnteredFormat.borders"
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row_index,
                    "endRowIndex": row_index + 1,
                    "startColumnIndex": 2,
                    "endColumnIndex": 3
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True}
                    }
                },
                "fields": "userEnteredFormat.textFormat.bold"
            }
        }
    ]
    service.spreadsheets().batchUpdate(
        spreadsheetId=id_sheet,
        body={"requests": requests}
    ).execute()

    return result