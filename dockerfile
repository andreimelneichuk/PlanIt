# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы приложения в контейнер
COPY . .

# Запуск FastAPI приложения
CMD ["uvicorn", "main:app","--reload", "--host", "0.0.0.0", "--port", "8000"]