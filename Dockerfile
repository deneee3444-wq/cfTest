FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Docker içinde root yetkisi olduğu için --with-deps sorunsuz kurulur
RUN playwright install --with-deps chromium
COPY . .
ENV PORT=5001
ENV RENDER=true
EXPOSE 5001
CMD ["python", "app.py"]
