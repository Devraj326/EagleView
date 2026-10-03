# Built from the REPO ROOT (not backend/), since the app imports snowflake_app/sf_lib
# via a sibling-directory sys.path insertion (see app/services/snowpark_service.py).
# docker build -f backend/Dockerfile -t <tag> .
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/app /app/backend/app
COPY snowflake_app/sf_lib /app/snowflake_app/sf_lib
COPY snowflake_app/demo_data /app/snowflake_app/demo_data

RUN mkdir -p /app/backend/storage/raw

WORKDIR /app/backend
EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
