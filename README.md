# ORBITRA — vahid tətbiq

ORBITRA virtual raket sınağı və telemetriya monitorinqi üçün bir FastAPI backend, bir React frontend və bir əsas SQLite bazası ilə işləyir. Lokal başlanğıc, hesablar və domen təlimatı üçün [START_HERE.md](START_HERE.md) sənədinə baxın. Əvvəlki iki tətbiqli quruluşun sənədi [docs/README_SPLIT_ARCHIVE.md](docs/README_SPLIT_ARCHIVE.md) faylında saxlanıb.

## Axın

`virtual` hesabı simulatoru idarə edir → backend hər nümunəni HMAC, format, sıra və sensor yoxlamasından keçirir → qəbul edilən nümunəni `backend/orbitra.db`-yə yazır → `admin` hesabının Mission Control ekranına WebSocket ilə ötürür. Rədd edilən test paketi qrafikə düşmür; təhlükəsizlik hadisəsi və Sentinel qərarı kimi saxlanır. AI yalnız qəbul edilmiş nümunələri qiymətləndirir.

Aktiv qovluqlar: `backend/`, `frontend/`, `backend/tests/`, `frontend/tests/`, `docs/`. Əvvəlki `device_backend/`, `device_frontend/` və bölünmə testləri layihədən kənarda `archive/split-apps/` qovluğuna köçürülüb; başlatma skripti və hosting onları işə salmır. Device bazasının köhnə run, göndəriş və audit tarixçəsi 0009 migrasiyasından sonra Main bazasına idempotent şəkildə köçürülür. Köhnə bazalar və kod ayrıca ehtiyat ZIP-də saxlanır.

Əvvəlki ssenarilər: `NORMAL_MISSION`, `TEMPERATURE_ANOMALY`, `INVALID_TELEMETRY`, `SINGLE_SENSOR_FAULT`, `INVALID_SIGNATURE`, `REPLAYED_TELEMETRY`. Yeni virtual test: `SPOOFED_TELEMETRY`. Üç təhlükəsizlik testi Virtual Device-də **Kiberhücum simulyasiyası** seçiminin altındadır; axın və hesabat qaydası [docs/CYBER_DEMO.md](docs/CYBER_DEMO.md) sənədində izah olunur.

Son dəyişikliklərin siyahısı və test nəticələri [CHANGELOG_CYBER_DEMO.md](CHANGELOG_CYBER_DEMO.md) faylındadır.
