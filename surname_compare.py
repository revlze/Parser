import pandas as pd
import itertools
import re
from collections import defaultdict
from rapidfuzz import fuzz

# === Конфигурация ===
CSV_PATH = "org_data/processed/14346/publications.csv"
FUZZ_THRESHOLD = 90  # чувствительность сравнения

# === Утилиты ===

def extract_last_name(full_name: str) -> str:
    """Оставляет только фамилию (первое слово)"""
    return re.split(r'\s+', full_name.strip())[0].lower()

def normalize(name: str) -> str:
    """Удаление точек, пробелов и приведение к нижнему регистру"""
    return re.sub(r'[.\s]', '', name.lower())

# === Загрузка и подготовка данных ===

df = pd.read_csv(CSV_PATH)
authors_raw = df['Authors'].dropna().tolist()
all_authors = list(itertools.chain.from_iterable(a.split(';') for a in authors_raw))
all_authors = sorted(set(a.strip() for a in all_authors if a.strip()))

# === Группировка по фамилии ===

# Сопоставим фамилии → полные формы
lastname_to_fullnames = defaultdict(set)
for full in all_authors:
    lname = extract_last_name(full)
    lastname_to_fullnames[lname].add(full)

# Построим пары на основе схожих фамилий
pairs = []
lastnames = sorted(lastname_to_fullnames.keys())

for i, lname1 in enumerate(lastnames):
    for lname2 in lastnames[i+1:]:
        sim = fuzz.ratio(lname1, lname2)
        if sim >= FUZZ_THRESHOLD:
            # Добавим все комбинации между полными именами
            for f1 in lastname_to_fullnames[lname1]:
                for f2 in lastname_to_fullnames[lname2]:
                    if f1 != f2:
                        pairs.append({'Label': f2, 'Replace by': f1})

# === Создание и сохранение файла ===

df_out = pd.DataFrame(pairs).drop_duplicates()
df_out.to_csv("thesaurus_authors_cleaned.csv", index=False, encoding='utf-8-sig')
print(f"Готово. Сохранено {len(df_out)} строк в thesaurus_authors_cleaned.csv")
