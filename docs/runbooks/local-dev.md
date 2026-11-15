# Local development

The commands are in `CLAUDE.md` and, with the common failures, in the `telcron-dev` skill.

- **Local admin.** Set `SEED_ADMIN_PASSWORD` in `.env.local` and run `uv run python -m app.seed` in
  `backend/`. That creates `admin@telcron.example.com` (role `admin`), and only when `ENV=local`. No admin
  credential is stored in the repository.
- **Verification codes.** With `DEV_EXPOSE_CODES=true` the sign-up screen shows both codes. Nothing is
  sent.
- **Coins.** `COIN_CONFIRM_DELAY_SECONDS=15` confirms coins after 15 seconds instead of 10 minutes.
- **Ports.** PostgreSQL :5436, Redis :6381, API :4310, web :3200. They are offset because other projects
  on the same machine use :5433, :5434, :6379 and :4100.
- **Tests** create and drop their own database, `telcron_test`, and use Redis database 1.
