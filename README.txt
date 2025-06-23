FAQ.

Как создать пользователя?

- Для этого нужно будет запустить docker и ввести команду:
docker compose exec backend python -m backend.app.manage -u super -p P@$sw0rd

Как кидать авторизованные запросы? (postman etc.)

- Нужно передавать header "Authorization: Bearer <токен>" в запросе.

// для обновления amvera