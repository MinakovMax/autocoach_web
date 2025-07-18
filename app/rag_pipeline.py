import os
import time
import requests

API_KEY = os.getenv("API_KEY")
BASE_URL = "https://speech2text.ru/api/recognitions"


def analyze_audio(file_path: str) -> str:
    """
    Отправляет аудиофайл в speech2text.ru, возвращает текст с именами спикеров.
    """
    if not API_KEY:
        raise Exception("API_KEY не задан. Укажите его в .env")

    with open(file_path, 'rb') as f:
        files = {'file': f}
        data = {
            'lang': 'ru',
            'speakers': '2'
        }
        url = f'{BASE_URL}/task/file?api-key={API_KEY}'
        response = requests.post(url, files=files, data=data)

    if not response.ok:
        raise Exception(f'Ошибка при отправке файла: {response.text}')

    task_id = response.json().get('id')
    if not task_id:
        raise Exception('Не удалось получить task_id из ответа')

    status_url = f'{BASE_URL}/{task_id}?api-key={API_KEY}'
    while True:
        status_response = requests.get(status_url)
        if not status_response.ok:
            raise Exception(f'Ошибка статуса: {status_response.text}')

        status_data = status_response.json()
        code = status_data.get('status', {}).get('code', 0)
        if code == 200:
            break
        elif code >= 500:
            raise Exception(f'Ошибка сервера: {status_data.get("status", {}).get("description", "")}')
        else:
            time.sleep(10)

    result_url = f'{BASE_URL}/{task_id}/result/json?api-key={API_KEY}'
    result_response = requests.get(result_url)

    if not result_response.ok:
        raise Exception(f'Ошибка получения результата: {result_response.text}')

    result_data = result_response.json()
    return format_dialogue(result_data)


def format_dialogue(data: dict) -> str:
    """
    Преобразует chunks + speakers в читаемый диалог.
    """
    speaker_map = {s['id']: s['name'] for s in data.get('speakers', [])}
    
    lines = []
    for chunk in data.get('chunks', []):
        speaker_id = chunk.get('speaker')
        speaker_name = speaker_map.get(speaker_id, f'Спикер {speaker_id}')
        text = chunk.get('text', '').strip()
        if text:
            lines.append(f"{speaker_name}: {text}")

    return '\n'.join(lines)

import os
import time
import jwt
import requests
from dotenv import load_dotenv
from langchain_community.llms import YandexGPT

load_dotenv()

# Получение переменных из .env
service_account_id = os.getenv('service_account_id')
key_id = os.getenv('key_id')
private_key = os.getenv('private_key').replace('\\n', '\n')
catalog_id = os.getenv('catalog_id')

# Генерация JWT и получение IAM токена
def get_iam_token():
    now = int(time.time())
    payload = {
        'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
        'iss': service_account_id,
        'iat': now,
        'exp': now + 360  # токен живёт 6 минут
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
    return data['iamToken']

# Генерация рекомендации
def generate_general(transcript: str) -> str:
    token = get_iam_token()

    llm = YandexGPT(
        model_uri=f"gpt://{catalog_id}/yandexgpt/latest",
        folder_id=catalog_id,
        iam_token=token,
        temperature=0.3,
        max_tokens=800,
    )

    prompt = f"""
Ты — эксперт по продажам. На основе следующего разговора с клиентом напиши рекомендации для менеджера по улучшению продаж. Укажи, что было хорошо, что можно улучшить и дай советы.

Разговор:
{transcript}

Структура ответа:
1. Что сделано хорошо.
2. Что можно улучшить.
3. Советы по эффективности.
"""
    return llm.invoke(prompt)

def generate_motivation(transcript: str) -> str:
    """
    Генерация мотивационной рекомендации на основе текста диалога.
    """
    token = get_iam_token()

    llm = YandexGPT(
        model_uri=f"gpt://{catalog_id}/yandexgpt/latest",
        folder_id=catalog_id,
        iam_token=token,
        temperature=0.4,
        max_tokens=800,
    )

    prompt = f"""
Ты — экспертный коуч по продажам с позитивным мышлением. На основе расшифровки диалога между продавцом и клиентом составь мотивационную рекомендацию для продавца.

🔹 Сделай упор на сильные стороны общения.  
🔹 Подчеркни моменты, где продавец проявил инициативу, эмпатию или настойчивость.  
🔹 Заверши текст вдохновляющим посылом, который зарядит его на результат и напомнит о важности его работы.

Используй дружелюбный, ободряющий тон. Не давай критики — только поддержка, похвала и мотивация.

Текст диалога:
\"\"\"
{transcript}
\"\"\"
"""

    return llm.invoke(prompt)


def generate_growth(transcript: str) -> str:
    """
    Генерация критической рекомендации и точек роста на основе текста диалога.
    """
    token = get_iam_token()

    llm = YandexGPT(
        model_uri=f"gpt://{catalog_id}/yandexgpt/latest",
        folder_id=catalog_id,
        iam_token=token,
        temperature=0.4,
        max_tokens=800,
    )

    prompt = f"""
Ты — эксперт по продажам и обучению сотрудников. Проанализируй диалог между продавцом и клиентом и выдай конструктивную обратную связь.

🔹 Укажи ключевые ошибки или упущенные возможности.  
🔹 Подчеркни моменты, где продавец мог бы действовать эффективнее.  
🔹 Сформулируй чёткие рекомендации по улучшению коммуникации и техники продаж.

Будь честен, конкретен и профессионален. Тон — уважительный, но ориентирован на рост и развитие.

Текст диалога:
\"\"\"
{transcript}
\"\"\"
"""

    return llm.invoke(prompt)

def generate_objection(transcript: str) -> str:
    """
    Генерация рекомендации по обработке возражений на основе текста диалога.
    """
    token = get_iam_token()

    llm = YandexGPT(
        model_uri=f"gpt://{catalog_id}/yandexgpt/latest",
        folder_id=catalog_id,
        iam_token=token,
        temperature=0.4,
        max_tokens=800,
    )

    prompt = f"""
Ты — эксперт по продажам с опытом в преодолении возражений. Проанализируй расшифровку диалога между продавцом и клиентом.

🔸 Выяви ключевые возражения, которые озвучил клиент или которые были явно не проработаны.  
🔸 Определи, насколько эффективно продавец отработал эти возражения.  
🔸 Предложи 2–3 варианта, как можно было бы отреагировать на каждое возражение более результативно.  
🔸 Используй деловой, обучающий тон, без критики личности — только анализ действий и профессиональные рекомендации.

Формат ответа:
1. Список выявленных возражений.
2. Краткий разбор текущей реакции продавца.
3. Альтернативные варианты более качественной обработки.

Текст диалога:
\"\"\"
{transcript}
\"\"\"
"""
    return llm.invoke(prompt)

