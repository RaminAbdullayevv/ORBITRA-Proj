# ORBITRA vahid tətbiq qeydi

Aktiv tətbiq `backend/` + `frontend/` və `backend/orbitra.db`-dir. Əvvəlki `device_backend/`, `device_frontend/` və bölünmə testləri layihədən kənarda `archive/split-apps/` qovluğunda saxlanır; təhvil ZIP-inə daxil edilmir, başlatma və deployment-də istifadə edilmir. Birləşmədən əvvəlki kod və hər iki bazanın nüsxəsi layihə qovluğundan kənarda `ORBITRA-before-unification-2026-10-27.zip` arxivindədir. `START_HERE.md` və `docs/DEPLOY.md` aktual başlatma sənədləridir.

Təhvil ZIP-də `.env`, HMAC açarı, `.venv`, `node_modules` və cache yoxdur. İlk başlatmada yeni HMAC açarı yaradılır; gələcək telemetriya onunla imzalanır. Əvvəlki qəbul edilmiş nümunələr, Sentinel qərarları və hesabat məlumatı bazada qalır, amma köhnə paketin imzasını yeni açarla yenidən hesablamaq mümkün deyil. Eyni köhnə açarla yoxlama tələb olunarsa, onu ayrıca təhlükəsiz kanalla köçürmək lazımdır. Ehtiyat ZIP-də əvvəlki lokal `.env` olduğu üçün onu ictimai paylaşmayın.
