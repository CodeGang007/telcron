# Local development

The commands are in `CLAUDE.md` and, with the common failures, in the `telcron-dev` skill.

- **Settings.** One file, `.env`, serves Docker Compose, `make` and the application.
- **Local admin.** Set `SEED_ADMIN_PASSWORD` in `.env` and run `uv run python -m app.seed` in `backend/`.
  That creates `admin@telcron.example.com` (role `admin`), and only when `ENV=local`. No admin credential
  is stored in the repository. The demo data's own accounts have no password.
- **Verification codes.** With `DEV_EXPOSE_CODES=true` the sign-up screen shows both codes. Nothing is sent.
- **Coins.** `COIN_CONFIRM_DELAY_SECONDS=15` makes the app seed shorten the earn rules' delay locally.
- **Ports.** PostgreSQL :5440 by default, Redis :6381, API :4310, web :3200. On a machine where other
  projects hold :5440 or :4100, set `DB_PORT` and `DATABASE_URL` in `.env`.
- **Tests** build and drop their own database, `telcron_api_test`, and use Redis database 1.
