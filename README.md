# portal-terminal
## Запуск проекта

*сделать git clone и перейти в главную папку проекта*

## По желанию можно запустить тесты, для этого надо

1) Перейти в главную папку проекта и установить виртуальное окружеение:
```
python -m venv venv

source venv/Scripts/activate
```

2) Установить зависимости

- закомментить строку в файле requirements.txt

- #psycopg2-binary==2.9.9

- устаносить зависимости

```
pip install -r requirements.txt
```

3) Прописать команду 

```
pytest
```


## Запуск через докер:

*запустить Flask-сервер с чеками*

*(не забыть при это раскомментить строку в файле зависимостей)*

```
docker compose build --no-cache
docker compose up -d

docker compose logs -f web (опционально)
docker compose logs -f db (опционально)
```
## Админка

Креды от админки:


- user: portal

- password: portal

- email: portal@portal.com


Креды можно изменить в Dockerfile


Админка находится по адресу:

- http://localhost:8000/admin

или

- http://127.0.0.1:8000/admin