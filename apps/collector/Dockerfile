FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Seoul

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
# 개발 의존성까지 설치한다. 같은 이미지를 앱 구동과 테스트에 모두 쓴다.
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api:build_default_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
