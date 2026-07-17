import re

def extract_google_id(url):
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    return match.group(1) if match else None

def get_file_content(service, file_id):
    # Метод execute() скачивает содержимое в оперативную память, но только для .txt, .csv, .pdf, .jpg, .zip
    content_bytes = service.files().get_media(fileId=file_id).execute()
    return content_bytes.decode('utf-8')


def row_to_dict(row_data):
    row_dict = {}
    for index, value in enumerate(row_data):
        column_letter = chr(ord('A') + index)
        row_dict[column_letter] = value
    return row_dict