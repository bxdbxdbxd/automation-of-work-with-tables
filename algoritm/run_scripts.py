from .file_access import extract_google_id, get_file_content
from .new_entry import add_row_to_sheet, cells_in_insert
from .read_file import parse_file, process_colors
from .sheet_file import find_value_in_sheet


SHEET_RANGE = "Лист1!A:R"


def build_design_link(file_id):
    return f"https://drive.google.com/file/d/{file_id}/view"


def content_design_by_id(service, file_id):
    content = get_file_content(service, file_id)
    designNum, barcode, colors_raw = parse_file(content)
    result_colors = process_colors(colors_raw)
    link_des = build_design_link(file_id)

    print(f"Дизайн: {designNum}")
    print(f"Баркод: {barcode}")
    print(f"Цвета: {result_colors}")

    return designNum, barcode, result_colors, link_des

def content_design(service):
    url_file = input('Ссылка на файл дизайна ')
    file_id = extract_google_id(url_file)
    if not file_id:
        raise ValueError("ID файла дизайна не найден в ссылке.")

    designNum, barcode, result_colors, _ = content_design_by_id(service, file_id)
    return designNum, barcode, result_colors, url_file


def content_one_tab_by_id(service, sheet_id, design_num):
    return find_value_in_sheet(service, sheet_id, SHEET_RANGE, design_num)

def content_one_tab(service, design_num):
    url_file_sheet = input('Ссылка на 1 таблицу ')
    sheet_id = extract_google_id(url_file_sheet)
    if not sheet_id:
        raise ValueError("ID первой таблицы не найден в ссылке.")
    return content_one_tab_by_id(service, sheet_id, design_num)


def content_second_tab_by_ids(
    sheets_service,
    drive_service,
    file_id,
    journal_id,
    base_id,
):
    designNum, barcode, colors, link_des = content_design_by_id(drive_service, file_id)
    info = content_one_tab_by_id(sheets_service, journal_id, designNum)
    if info is None:
        raise ValueError(f"Дизайн {designNum} не найден в таблице-журнале.")

    info['E'] = designNum
    row_list = cells_in_insert(info, barcode, colors, link_des)
    return add_row_to_sheet(sheets_service, base_id, row_list)

def content_second_tab(sheets_service, drive_service):
    designNum, barcode, colors, link_des = content_design(drive_service)
    info = content_one_tab(sheets_service, designNum)
    if info is None:
        raise ValueError(f"Дизайн {designNum} не найден в таблице-журнале.")
    info['E'] = designNum
    url_file_sheet2 = input('Ссылка на 2 таблицу ')
    sheet_id = extract_google_id(url_file_sheet2)
    if not sheet_id:
        raise ValueError("ID второй таблицы не найден в ссылке.")
    row_list = cells_in_insert(info, barcode, colors, link_des)
    return add_row_to_sheet(sheets_service, sheet_id, row_list)