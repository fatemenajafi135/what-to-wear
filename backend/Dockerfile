FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY . .

RUN uv pip install -e .

EXPOSE 8000

CMD ["uvicorn", "whattowear.main:app", "--host", "0.0.0.0", "--port", "8000"]