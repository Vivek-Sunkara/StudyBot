def detect_script(text):
    counts = {
        "Telugu": 0, "Hindi": 0, "Tamil": 0, "Kannada": 0,
        "Malayalam": 0, "Bengali": 0, "Gujarati": 0,
        "Gurmukhi": 0, "Latin": 0
    }
    for ch in text:
        n = ord(ch)
        if 0x0C00 <= n <= 0x0C7F: counts["Telugu"] += 1
        elif 0x0900 <= n <= 0x097F: counts["Hindi"] += 1
        elif 0x0B80 <= n <= 0x0BFF: counts["Tamil"] += 1
        elif 0x0C80 <= n <= 0x0CFF: counts["Kannada"] += 1
        elif 0x0D00 <= n <= 0x0D7F: counts["Malayalam"] += 1
        elif 0x0980 <= n <= 0x09FF: counts["Bengali"] += 1
        elif 0x0A80 <= n <= 0x0AFF: counts["Gujarati"] += 1
        elif 0x0A00 <= n <= 0x0A7F: counts["Gurmukhi"] += 1
        elif ("A" <= ch <= "Z") or ("a" <= ch <= "z"): counts["Latin"] += 1
    for name in ("Telugu","Hindi","Tamil","Kannada","Malayalam","Bengali","Gujarati","Gurmukhi"):
        if counts[name]:
            return name
    return "English/Latin" if counts["Latin"] else "Unknown"
