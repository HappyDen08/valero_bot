.PHONY: up down build recreate restart logs log-web log-bot log-db log-backup ps shell dbshell migrate makemigrations superuser collectstatic backup seed clean-seed

up:            ## підняти весь стек (локально, без https)
	docker compose up -d

up-prod:       ## підняти стек на сервері разом з Caddy (https)
	docker compose --profile prod up -d --build

down:          ## зупинити все
	docker compose down

build:         ## перезібрати образи
	docker compose build

recreate:      ## перезібрати і перестворити контейнери (код у образі)
	docker compose up -d --build --force-recreate

restart:       ## перезапустити без перезбирання
	docker compose restart

logs:          ## логи всіх сервісів (follow)
	docker compose logs -f --tail 100

log-web:
	docker compose logs -f --tail 100 web

log-bot:
	docker compose logs -f --tail 100 bot

log-db:
	docker compose logs -f --tail 100 db

log-backup:
	docker compose logs -f --tail 100 backup

ps:            ## статус контейнерів
	docker compose ps

shell:         ## Django shell
	docker compose exec web python manage.py shell

dbshell:       ## psql до бази
	docker compose exec db psql -U $${POSTGRES_USER:-veloro} -d $${POSTGRES_DB:-veloro}

migrate:
	docker compose exec web python manage.py migrate

makemigrations migrations:
	docker compose exec web python manage.py makemigrations

superuser:     ## створити адміна панелі
	docker compose exec web python manage.py createsuperuser

collectstatic:
	docker compose exec web python manage.py collectstatic --noinput

backup:        ## ручний бекап БД + media
	docker compose exec backup /backup.sh

seed:          ## демо-дані (50 учасників)
	docker compose exec -T web python manage.py shell < scripts/seed_demo.py

help:          ## список команд
	@grep -E '^[a-z-]+:.*##' Makefile | sed 's/:.*##/ —/'
