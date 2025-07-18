import os
import time
import statistics
import requests
import jwt
from dotenv import load_dotenv

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import YandexGPTEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Загрузка переменных окружения
load_dotenv()

# Переменные из .env
service_account_id = os.getenv('service_account_id')
key_id = os.getenv('key_id')
private_key = os.getenv('private_key').replace('\\n', '\n')
catalog_id = os.getenv('catalog_id')

# Получение IAM токена
now = int(time.time())
payload = {
    'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
    'iss': service_account_id,
    'iat': now,
    'exp': now + 360
}

encoded_token = jwt.encode(
    payload,
    private_key,
    algorithm='PS256',
    headers={'kid': key_id}
)

response = requests.post(
    'https://iam.api.cloud.yandex.net/iam/v1/tokens',
    headers={'Content-Type': 'application/json'},
    json={'jwt': encoded_token}
)

data = response.json()
print("Ответ от Yandex:", data)
token = data['iamToken']

# Путь к главам
chapters_path = os.path.join(os.path.dirname(__file__), "chapsters")
assert os.path.isdir(chapters_path), f"Папка {chapters_path} не найдена."

# Загрузка .txt-файлов
documents = []
for filename in os.listdir(chapters_path):
    if filename.endswith(".txt"):
        loader = TextLoader(os.path.join(chapters_path, filename), encoding="utf-8")
        docs = loader.load()
        documents.extend(docs)

# Разделение на чанки
text_splitter = RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=300)
dataset = text_splitter.split_documents(documents)

# Статистика
lengths = [len(doc.page_content) for doc in dataset]
print(f"Всего документов: {len(dataset)} | Средняя длина: {int(statistics.mean(lengths))}")

# Векторизация
embeddings = YandexGPTEmbeddings(
    iam_token=token,
    folder_id=catalog_id,  # <-- как у серв. аккаунта
    sleep_interval=0.1
)

# Сохранение/загрузка индекса
index_path = os.path.join(os.path.dirname(__file__), "travel_store")
if os.path.exists(index_path):
    storage = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
    print("✅ Индекс загружен с диска.")
else:
    storage = FAISS.from_documents(dataset, embedding=embeddings)
    storage.save_local(index_path)
    print("✅ Индекс создан и сохранён.")
