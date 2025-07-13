FAQ.

# Как создать пользователя?

- Для этого нужно будет запустить docker и ввести команду:
docker compose exec backend python -m backend.app.manage -u admin -p PUdq5VhN4I4h

# Как кидать авторизованные запросы? (postman etc.)

- Нужно передавать header "Authorization: Bearer <токен>" в запросе.

# Как подключиться к postgres?

PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -d postgres
Или
docker compose exec db psql -U postgres -d postgres 

# Генерация и применение миграций.

docker compose run backend alembic revision --autogenerate -m "init"
docker compose run backend alembic upgrade head