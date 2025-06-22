Как создать пользователя?

Для этого нужно будет запустить docker и ввести команду:
docker compose exec backend python -m backend.app.manage -u <имя пользователя> -p <пароль>