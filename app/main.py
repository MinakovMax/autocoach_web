from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import PlainTextResponse
import uuid
import os
from app.rag_pipeline import analyze_audio, generate_general, generate_motivation, generate_growth, generate_objection
import shutil
from app.db import save_recommendation, SessionLocal, Conversation


app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

AUDIO_DIR = "audiofiles"
os.makedirs(AUDIO_DIR, exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def read_form(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "status": None})


@app.post("/upload", response_class=HTMLResponse)
async def upload_file(request: Request, file: UploadFile = File(...)):
    if not file.filename.endswith((".mp3", ".wav")):
        return templates.TemplateResponse("index.html", {
            "request": request,
            "status": "error",
            "message": "Загрузите .mp3 или .wav файл.",
        })

    # Сохраняем аудиофайл
    filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(AUDIO_DIR, filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Распознаём аудио в текст
    try:
        transcript = analyze_audio(file_path)
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "status": "error",
            "message": f"Ошибка обработки: {str(e)}",
        })

    # Сохраняем результат в базу
    try:
        db = SessionLocal()
        conv = Conversation(
            filename=filename,
            transcript=transcript
        )
        db.add(conv)
        db.commit()
        db.close()
    except Exception as db_error:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "status": "error",
            "message": f"Ошибка при сохранении в БД: {str(db_error)}",
        })

    # Показываем результат пользователю
    return templates.TemplateResponse("index.html", {
        "request": request,
        "status": "complete",
        "text": transcript
    })


@app.post("/recommend/general", response_class=PlainTextResponse)
async def recommend_general(transcript: str = Form(...)):
    result = generate_general(transcript)
    save_recommendation(transcript, result, "general")
    return result

@app.post("/recommend/motivation", response_class=PlainTextResponse)
async def recommend_motivation(transcript: str = Form(...)):
    result = generate_motivation(transcript)
    save_recommendation(transcript, result, "motivation")
    return result

@app.post("/recommend/growth", response_class=PlainTextResponse)
async def recommend_growth(transcript: str = Form(...)):
    result = generate_growth(transcript)
    save_recommendation(transcript, result, "growth")
    return result

@app.post("/recommend/objection", response_class=PlainTextResponse)
async def recommend_objection(transcript: str = Form(...)):
    result = generate_objection(transcript)
    save_recommendation(transcript, result, "objection")
    return result