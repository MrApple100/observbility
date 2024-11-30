FROM python:3.10

WORKDIR /code

COPY requirements.txt /code/
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY . /code/app

EXPOSE 8000

# Копирование файлов alembic
COPY ./migrations /code/migrations
COPY ./alembic.ini /code/alembic.ini
COPY ./entrypoint.sh /code/entrypoint.sh

ENTRYPOINT ["/code/entrypoint.sh"]

##CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
