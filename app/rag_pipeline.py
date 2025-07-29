import os
import time
import requests
import logging
import traceback

# --- Настройка логгера ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("speech2text_app")

API_KEY = os.getenv("API_KEY")
BASE_URL = "https://speech2text.ru/api/recognitions"

def analyze_audio(file_path: str) -> str:
    logger.info(f"Старт анализа аудиофайла: {file_path}")

    if not API_KEY:
        logger.error("API_KEY не задан. Укажите его в .env")
        raise Exception("API_KEY не задан. Укажите его в .env")

    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {'lang': 'ru', 'speakers': '2'}
            url = f'{BASE_URL}/task/file?api-key={API_KEY}'
            response = requests.post(url, files=files, data=data, timeout=60)
        logger.info(f"Файл успешно отправлен, статус: {response.status_code}")
    except FileNotFoundError:
        logger.error(f"Файл не найден: {file_path}")
        raise
    except Exception as ex:
        logger.error(f"Ошибка при отправке файла: {ex}\n{traceback.format_exc()}")
        raise

    if not response.ok:
        logger.error(f'Ошибка при отправке файла: {response.text}')
        raise Exception(f'Ошибка при отправке файла: {response.text}')

    try:
        resp_json = response.json()
        task_id = resp_json.get('id')
    except Exception:
        logger.error(f"Ошибка чтения JSON: {response.text}")
        raise

    if not task_id:
        logger.error("Не удалось получить task_id из ответа")
        raise Exception('Не удалось получить task_id из ответа')

    status_url = f'{BASE_URL}/{task_id}?api-key={API_KEY}'
    logger.info(f"Запрошен статус задачи: {task_id}")

    for i in range(60):  # 10 минут ожидания
        try:
            status_response = requests.get(status_url, timeout=30)
        except Exception as ex:
            logger.error(f"Ошибка запроса статуса: {ex}\n{traceback.format_exc()}")
            raise
        if not status_response.ok:
            logger.error(f'Ошибка статуса: {status_response.text}')
            raise Exception(f'Ошибка статуса: {status_response.text}')
        try:
            status_data = status_response.json()
        except Exception:
            logger.error(f"Ошибка чтения JSON статуса: {status_response.text}")
            raise
        code = status_data.get('status', {}).get('code', 0)
        if code == 200:
            logger.info("Аудиофайл успешно распознан, получаем результат.")
            break
        elif code >= 500:
            logger.error(f'Ошибка сервера: {status_data.get("status", {}).get("description", "")}')
            raise Exception(f'Ошибка сервера: {status_data.get("status", {}).get("description", "")}')
        else:
            logger.debug(f"Ожидание завершения задачи, попытка {i+1}/60")
            time.sleep(10)
    else:
        logger.error('Истекло время ожидания обработки файла')
        raise Exception('Истекло время ожидания обработки файла')

    result_url = f'{BASE_URL}/{task_id}/result/json?api-key={API_KEY}'
    try:
        result_response = requests.get(result_url, timeout=60)
    except Exception as ex:
        logger.error(f"Ошибка получения результата: {ex}\n{traceback.format_exc()}")
        raise

    if not result_response.ok:
        logger.error(f'Ошибка получения результата: {result_response.text}')
        raise Exception(f'Ошибка получения результата: {result_response.text}')

    try:
        result_data = result_response.json()
    except Exception:
        logger.error(f"Ошибка чтения JSON результата: {result_response.text}")
        raise

    try:
        dialogue = format_dialogue(result_data)
        logger.info("Диалог успешно сформирован.")
        return dialogue
    except Exception as ex:
        logger.error(f"Ошибка форматирования диалога: {ex}\n{traceback.format_exc()}")
        raise

def format_dialogue(data: dict) -> str:
    speaker_map = {s['id']: s['name'] for s in data.get('speakers', [])}
    lines = []
    for chunk in data.get('chunks', []):
        speaker_id = chunk.get('speaker')
        speaker_name = speaker_map.get(speaker_id, f'Спикер {speaker_id}')
        text = chunk.get('text', '').strip()
        if text:
            lines.append(f"{speaker_name}: {text}")
    return '\n'.join(lines)

# --- Дальше логика работы с YandexGPT ---

import jwt
from dotenv import load_dotenv
from langchain_community.llms import YandexGPT

load_dotenv()

service_account_id = os.getenv('service_account_id')
key_id = os.getenv('key_id')
private_key = os.getenv('private_key')
catalog_id = os.getenv('catalog_id')

if private_key:
    private_key = private_key.replace('\\n', '\n')

def get_iam_token():
    if not all([service_account_id, key_id, private_key]):
        logger.error("service_account_id, key_id или private_key не заданы в .env")
        raise Exception("service_account_id, key_id или private_key не заданы в .env")
    now = int(time.time())
    payload = {
        'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
        'iss': service_account_id,
        'iat': now,
        'exp': now + 360
    }
    try:
        encoded_token = jwt.encode(
            payload,
            private_key,
            algorithm='PS256',
            headers={'kid': key_id}
        )
        logger.info("JWT успешно сгенерирован")
    except Exception as ex:
        logger.error(f"Ошибка генерации JWT: {ex}\n{traceback.format_exc()}")
        raise

    try:
        response = requests.post(
            'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            headers={'Content-Type': 'application/json'},
            json={'jwt': encoded_token},
            timeout=30
        )
        data = response.json()
        if "iamToken" not in data:
            logger.error(f"Ответ не содержит iamToken: {data}")
            raise Exception(f"Ответ не содержит iamToken: {data}")
        logger.info("IAM токен успешно получен")
        return data['iamToken']
    except Exception as ex:
        logger.error(f"Ошибка получения IAM токена: {ex}\n{traceback.format_exc()}")
        raise

def safe_llm_invoke(llm, prompt: str):
    try:
        logger.info("Отправляем prompt в YandexGPT")
        return llm.invoke(prompt)
    except Exception as ex:
        logger.error(f"Ошибка генерации текста (invoke): {ex}\n{traceback.format_exc()}")
        raise

def generate_general(transcript: str) -> str:
    try:
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
        return safe_llm_invoke(llm, prompt)
    except Exception as ex:
        logger.error(f"Ошибка генерации рекомендации (general): {ex}")
        return f"[ОШИБКА] {ex}"

def generate_motivation(transcript: str) -> str:
    try:
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
\"\"\"{transcript}\"\"\"
"""
        return safe_llm_invoke(llm, prompt)
    except Exception as ex:
        logger.error(f"Ошибка генерации мотивации: {ex}")
        return f"[ОШИБКА] {ex}"

def generate_growth(transcript: str) -> str:
    try:
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
\"\"\"{transcript}\"\"\"
"""
        return safe_llm_invoke(llm, prompt)
    except Exception as ex:
        logger.error(f"Ошибка генерации точки роста: {ex}")
        return f"[ОШИБКА] {ex}"

def generate_objection(transcript: str) -> str:
    try:
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
\"\"\"{transcript}\"\"\"
"""
        return safe_llm_invoke(llm, prompt)
    except Exception as ex:
        logger.error(f"Ошибка генерации по возражениям: {ex}")
        return f"[ОШИБКА] {ex}"

