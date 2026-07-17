from .file_access import row_to_dict


def find_value_in_sheet(sheets_service, file_id, range_name, target_value):
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=file_id,
        range=range_name
    ).execute()

    rows = result.get('values', [])
    search_term = target_value
    if search_term.endswith('K'):
        search_term = search_term[:-1]

    found_row_data = None
    for row in rows:
        if target_value in row or search_term in row:
            found_row_data = row
            break

    if found_row_data:
        row_dict = row_to_dict(found_row_data)
        print("Найдено совпадение для:", search_term)
        print("Значение в столбцах P, Q, J, K:", row_dict.get('P'), row_dict.get('Q'), row_dict.get('J'),
              row_dict.get('K'))
    else:
        print("Ничего не найдено для", search_term)
        return None

    return row_dict