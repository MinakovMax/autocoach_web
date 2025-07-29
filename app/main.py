from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uuid
import os
import logging
import shutil
from app.rag_pipeline import analyze_audio, generate_general, generate_motivation, generate_growth, generate_objection
from app.db import save_recommendation, SessionLocal, Conversation

# --- Логирование ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("fastapi_app")

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

AUDIO_DIR = "audiofiles"
os.makedirs(AUDIO_DIR, exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def read_form(request: Request):
    logger.info("GET / — Отображение формы загрузки")
    return templates.TemplateResponse("index.html", {"request": request, "status": None})

MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 МБ в байтах

@app.post("/upload", response_class=HTMLResponse)
async def upload_file(request: Request, file: UploadFile = File(...)):
    logger.info(f"POST /upload — Получен файл: {file.filename}")

    if not file.filename.endswith((".mp3", ".wav")):
        logger.warning(f"Загружен файл неподходящего типа: {file.filename}")
        return templates.TemplateResponse("index.html", {
            "request": request,
            "status": "error",
            "message": "Загрузите .mp3 или .wav файл.",
        })

    # --- ПРОВЕРКА РАЗМЕРА ---
    contents = await file.read()
    file_size = len(contents)
    if file_size > MAX_FILE_SIZE:
        logger.warning(f"Загружен слишком большой файл: {file.filename} ({file_size} байт)")
        return templates.TemplateResponse("index.html", {
            "request": request,
            "status": "error",
            "message": "Файл превышает 15 МБ. Пожалуйста, загрузите файл меньшего размера.",
        })
    # Сбросить указатель (так как файл уже считан)
    file.file.seek(0)

    # Сохраняем аудиофайл
    filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(AUDIO_DIR, filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"Аудиофайл сохранён: {file_path}")
    except Exception as file_error:
        logger.error(f"Ошибка при сохранении аудиофайла: {file_error}")
        return templates.TemplateResponse("index.html", {
            "request": request,
            "status": "error",
            "message": "Ошибка при сохранении файла. Попробуйте ещё раз.",
        })

    # Далее как было...
    try:
        logger.info(f"Начинаем распознавание аудио: {file_path}")
        transcript = analyze_audio(file_path)
        logger.info("Распознавание аудио завершено")
    except Exception as e:
        logger.error(f"Ошибка при анализе аудио: {e}")
        return templates.TemplateResponse("index.html", {
            "request": request,
            "status": "error",
            "message": f"Ошибка обработки: {str(e)}",
        })

    try:
        db = SessionLocal()
        conv = Conversation(
            filename=filename,
            transcript=transcript
        )
        db.add(conv)
        db.commit()
        db.close()
        logger.info(f"Результат сохранён в БД для файла {filename}")
    except Exception as db_error:
        logger.error(f"Ошибка при сохранении в БД: {db_error}")
        return templates.TemplateResponse("index.html", {
            "request": request,
            "status": "error",
            "message": "Ошибка при сохранении в базу данных.",
        })

    logger.info("Загрузка и обработка завершены успешно")
    return templates.TemplateResponse("index.html", {
        "request": request,
        "status": "complete",
        "text": transcript
    })


@app.post("/recommend/general", response_class=PlainTextResponse)
async def recommend_general(transcript: str = Form(...)):
    logger.info("POST /recommend/general")
    try:
        result = generate_general(transcript)
        save_recommendation(transcript, result, "general")
        logger.info("Рекомендация 'general' успешно сгенерирована и сохранена")
        return result
    except Exception as e:
        logger.error(f"Ошибка при генерации/сохранении 'general': {e}")
        return PlainTextResponse(f"Ошибка генерации рекомендации: {e}", status_code=500)

@app.post("/recommend/motivation", response_class=PlainTextResponse)
async def recommend_motivation(transcript: str = Form(...)):
    logger.info("POST /recommend/motivation")
    try:
        result = generate_motivation(transcript)
        save_recommendation(transcript, result, "motivation")
        logger.info("Рекомендация 'motivation' успешно сгенерирована и сохранена")
        return result
    except Exception as e:
        logger.error(f"Ошибка при генерации/сохранении 'motivation': {e}")
        return PlainTextResponse(f"Ошибка генерации рекомендации: {e}", status_code=500)

@app.post("/recommend/growth", response_class=PlainTextResponse)
async def recommend_growth(transcript: str = Form(...)):
    logger.info("POST /recommend/growth")
    try:
        result = generate_growth(transcript)
        save_recommendation(transcript, result, "growth")
        logger.info("Рекомендация 'growth' успешно сгенерирована и сохранена")
        return result
    except Exception as e:
        logger.error(f"Ошибка при генерации/сохранении 'growth': {e}")
        return PlainTextResponse(f"Ошибка генерации рекомендации: {e}", status_code=500)

@app.post("/recommend/objection", response_class=PlainTextResponse)
async def recommend_objection(transcript: str = Form(...)):
    logger.info("POST /recommend/objection")
    try:
        result = generate_objection(transcript)
        save_recommendation(transcript, result, "objection")
        logger.info("Рекомендация 'objection' успешно сгенерирована и сохранена")
        return result
    except Exception as e:
        logger.error(f"Ошибка при генерации/сохранении 'objection': {e}")
        return PlainTextResponse(f"Ошибка генерации рекомендации: {e}", status_code=500)
