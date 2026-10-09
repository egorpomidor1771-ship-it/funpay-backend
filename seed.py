import re
import requests
import random
import time

# ⚠️ Заливаем НАПРЯМУЮ в локальный backend (не через туннель)
API_URL = "https://dedok2144.pythonanywhere.com"
INPUT_FILE = "nemo.txt"


def random_rating():
    r = random.random()
    if r < 0.75: return 5
    elif r < 0.97: return 4
    else: return random.choice([3, 2])


def read_file_auto(path):
    encodings = ['utf-8-sig', 'utf-8', 'cp1251', 'windows-1251', 'utf-16']
    best_content = None; best_score = -1; best_enc = None
    for enc in encodings:
        try:
            with open(path, 'r', encoding=enc, errors='replace') as f:
                content = f.read()
            cyrillic = len(re.findall(r'[а-яА-ЯёЁ]', content))
            garbage = content.count('Рї') + content.count('СЂ') + content.count('Рѕ')
            score = cyrillic - garbage * 10
            print(f"  {enc}: кириллица={cyrillic}, мусор={garbage}, оценка={score}")
            if score > best_score:
                best_score = score; best_content = content; best_enc = enc
        except (UnicodeDecodeError, LookupError):
            continue
    print(f"✅ Выбрана кодировка: {best_enc}")
    return best_content


def parse_reviews(text):
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = [l.rstrip() for l in text.split('\n')]
    reviews = []; i = 0; n = len(lines)
    while i < n:
        while i < n and not lines[i].strip(): i += 1
        if i >= n: break
        nickname = lines[i].strip(); i += 1
        while i < n and not lines[i].strip(): i += 1
        if i >= n: break
        gift = lines[i].strip(); i += 1
        while i < n and not lines[i].strip(): i += 1
        if i >= n: break
        text_lines = []; date_line = None
        while i < n:
            line = lines[i].strip()
            if not line: i += 1; continue
            if re.search(r'\b20\d{2}\b', line): date_line = line; i += 1; break
            text_lines.append(line); i += 1
        if not date_line: continue
        review_text = ' '.join(text_lines).strip()
        if not review_text: continue
        reviews.append({
            "rating": random_rating(),
            "nickname": nickname, "gift": gift, "text": review_text,
            "created_at": date_line
        })
    return reviews


def main():
    print(f"Читаю файл {INPUT_FILE}...")
    try:
        content = read_file_auto(INPUT_FILE)
    except FileNotFoundError:
        print(f"❌ Файл {INPUT_FILE} не найден")
        return
    reviews = parse_reviews(content)
    print(f"\n✅ Распарсено {len(reviews)} отзывов")
    if not reviews:
        return

    ans = input(f"Залить {len(reviews)} отзывов? (y/n): ").strip().lower()
    if ans != 'y':
        return

    print(f"Очищаю старые отзывы на {API_URL}...")
    try:
        r = requests.delete(f"{API_URL}/admin/reviews", timeout=30)
        print(f"Очистка: {r.status_code}")
    except Exception as e:
        print(f"Ошибка очистки: {e}")
        return

    BATCH = 200
    total_added = 0
    for i in range(0, len(reviews), BATCH):
        batch = reviews[i:i+BATCH]
        print(f"Пачка {i//BATCH+1} ({len(batch)} шт)...", end=" ", flush=True)
        try:
            r = requests.post(f"{API_URL}/admin/seed-reviews", json=batch, timeout=60)
            if r.status_code == 200:
                d = r.json(); total_added += d.get("added", 0)
                print(f"✅ {d.get('added', 0)}")
            else:
                print(f"❌ {r.status_code}")
        except Exception as e:
            print(f"❌ {e}")
    print(f"\n🎉 Готово! Всего: {total_added} отзывов")


if __name__ == "__main__":
    main()