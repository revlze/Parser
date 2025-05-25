import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from transliterate import translit

INPUT_FILE = "org_data/processed/14346/publications.csv"
OUTPUT_FILE = "org_data/processed/14346/thesaurus_authors.txt"
SIMILARITY_COEFFICIENT = 0.8  # можно изменить
SURNAME_DIFF = 3  # можно изменить

print("Загрузка данных...")
df = pd.read_csv(INPUT_FILE)

print("Обработка авторов...")
authors = df['Authors'].dropna()
authors = authors.str.split('; ').explode()
authors = authors.drop_duplicates().reset_index(drop=True)

X = pd.DataFrame({'Authors': authors})
X['Ready'] = authors.str.lower().str.replace(r'[^а-яa-z .]', '', regex=True)

def transliterate_name(name):
    if len(name) > 0:
        if name[-1] == '.':
            name = name[:-1]
        arr = name.split()
        name = arr[0] + ' ' + ''.join(arr[1:])
    return translit(name, 'ru', reversed=True)

X['Ready'] = X['Ready'].apply(transliterate_name)

# Разделение фамилии и инициалов
X['Surnames'] = X['Ready'].apply(lambda x: x.split()[0] if len(x.split()) > 0 else '')
X['Initials'] = X['Ready'].apply(lambda x: x.split()[1] if len(x.split()) > 1 else '')

# Алгоритм поиска похожих фамилий
print("Поиск похожих фамилий...")
vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(1, 2))  # ngram_range можно изменить
matrix = vectorizer.fit_transform(X['Surnames'])
similarity = cosine_similarity(matrix)

# Сборка тезауруса
print("Сборка тезауруса...")
thesaurus = {}
total = len(similarity)

for i in range(total):
    if X['Authors'][i] in thesaurus:
        continue
        
    if (i + 1) % 100 == 0:
        print(f"Обработано: {i+1}/{total}")
        
    for j in range(i+1, total):
        if X['Authors'][j] in thesaurus:
            continue
            
        if similarity[i][j] < SIMILARITY_COEFFICIENT:
            continue
            
        # Проверка инициалов
        initials1 = X['Initials'][i].split('.')
        initials2 = X['Initials'][j].split('.')
        
        if len(initials1) != len(initials2):
            shorter, longer = sorted([initials1, initials2], key=len)
            if shorter != longer[:len(shorter)]:
                continue
        elif initials1 != initials2:
            continue
            
        # Проверка фамилий
        surname1, surname2 = X['Surnames'][i], X['Surnames'][j]
        if abs(len(surname1) - len(surname2)) > SURNAME_DIFF:
            continue
            
        if (surname1[-1] == 'a') ^ (surname2[-1] == 'a'):  # XOR для проверки мужская/женская фамилия
            continue
            
        thesaurus[X['Authors'][j]] = X['Authors'][i]

# Сохранение
print("Сохранение в файл...")
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write("Label\tReplace by\n")
    for label, replace_by in thesaurus.items():
        f.write(f"{label}\t{replace_by}\n")

print("Готово! Результаты сохранены в", OUTPUT_FILE)
