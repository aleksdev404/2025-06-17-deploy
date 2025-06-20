FROM python:3.11-slim

# 1. Переменные окружения (убираем bytecode, ускоряем pip)
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 2. Установка зависимостей
COPY backend/requirements.txt .
RUN python -m pip install --upgrade pip && \
    pip install -r requirements.txt

# 3. Копируем код
COPY backend /app/backend
COPY frontend /app/frontend    

EXPOSE 8000

# 4. Запуск
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
