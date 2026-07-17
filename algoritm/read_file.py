def parse_file(file_content):
    lines = [line.strip() for line in file_content.splitlines()]
    if len(lines) < 3:
        raise ValueError(
            "Файл дизайна должен содержать минимум 3 строки: "
            "номер дизайна, штрихкод и цвета."
        )
    designNum = lines[0]
    barcode = lines[1]
    colors_raw = lines[2]
    return designNum, barcode, colors_raw

def process_colors(colors_raw):
    string_colors = {}
    for pos in colors_raw.split():
        string_colors[pos] = pos
    for sym in 'CMYK':
        if string_colors.get(sym) is None:
            string_colors[sym] = ''
    return string_colors
