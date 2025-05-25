import pandas as pd
from rapidfuzz import process, fuzz
import itertools

csv_path = "org_data/processed/14346/publications.csv"
df = pd.read_csv(csv_path)

# Сбор и очистка авторов
all_authors = df['Authors'].dropna().tolist()
author_list = list(itertools.chain.from_iterable(a.split(';') for a in all_authors))
author_list = list(set(a.strip() for a in author_list if a.strip()))

# Функция для разбиения на фамилию и инициалы
def split_name(full_name):
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return parts[0], parts[1]  # Фамилия, инициалы
    else:
        return parts[0], ''  # На случай "Марков"

seen_pairs = set()
pairs = []

for author in author_list:
    matches = process.extract(author, author_list, scorer=fuzz.ratio, limit=10)
    for match, score, _ in matches:
        if match == author or score <= 92:
            continue

        fam1, init1 = split_name(author)
        fam2, init2 = split_name(match)

        # Добавляем только если фамилия совпадает, но инициалы (строго) тоже совпадают
        if fam1 == fam2 and init1 != init2:
            continue  # Имена разные — не добавляем

        a1, a2 = sorted([author, match])
        if (a1, a2) not in seen_pairs:
            seen_pairs.add((a1, a2))
            pairs.append({"Автор": a1, "Похожие варианты": a2, "Сходство": score})

# Сохраняем
similar_df = pd.DataFrame(pairs)
similar_df.to_csv("similar_authors_filtered.csv", index=False, encoding='utf-8')
print("Сохранено в similar_authors_filtered.csv с фильтрацией по инициалам")
