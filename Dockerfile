FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Chromium ve CloakBrowser için gerekli tüm Linux sistem kütüphanelerini kur
RUN playwright install --with-deps chromium

# CloakBrowser'ın stealth Chromium binary'sini Docker build aşamasında indirip hazırla
RUN python -c "import cloakbrowser; cloakbrowser.ensure_binary()"

COPY . .

ENV PORT=5001
ENV RENDER=true

EXPOSE 5001

CMD ["python", "app.py"]
