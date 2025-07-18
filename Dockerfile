################### builder ###################
FROM python:3.10 AS builder
WORKDIR /app

# Установка системных зависимостей для сборки
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev

# Установка Python-зависимостей
COPY requirements.txt .
RUN python -m pip install --upgrade pip
RUN pip install --prefix=/opt/deps --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

################### runtime ###################
FROM python:3.10-slim AS runtime
WORKDIR /app

# Установка минимального набора системных библиотек
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev libgomp1 && \
    rm -rf /var/lib/apt/lists/*

# Копируем зависимости и код из builder
COPY --from=builder /opt/deps /opt/deps
COPY --from=builder /app /app

# Устанавливаем переменные окружения для python и PATH
ENV PYTHONPATH=/opt/deps/lib/python3.10/site-packages
ENV PATH=/opt/deps/bin:$PATH

# Запуск приложения
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]