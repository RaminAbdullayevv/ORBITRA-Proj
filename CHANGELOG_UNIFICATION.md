# ORBITRA vahid tətbiqə birləşdirmə

## Nə dəyişdi

- Aktiv tətbiq `backend/` + `frontend/` oldu; `device_backend/` və `device_frontend/` layihədən kənarda `archive/split-apps/` qovluğuna köçürüldü, təhvil paketində yoxdur. Əvvəlki ZIP `ORBITRA-before-unification-2026-10-27.zip` layihədən kənarda qorunur.
- `backend/app/main.py` bir backend-də simulator marşrutunu, monitorinq API-lərini, bir giriş sistemini və yığılmış frontend-i birləşdirir. Əvvəlki Device → Main HTTP ingress marşrutu artıq tətbiqə qoşulmur.
- `backend/app/auth.py`, `backend/app/api/auth_routes.py`, `backend/app/api/simulator_routes.py`, `backend/app/api/telemetry_routes.py` və monitorinq router-ləri `VIRTUAL` və monitorinq rollarını HTTP/WebSocket səviyyəsində ayırır. Eyni brauzerdə hesab dəyişəndə köhnə sessiya ləğv olunur; çıxış açıq WebSocket-ləri bağlayır.
- `backend/app/telemetry.py` mövcud imzalı paket yoxlamasını daxili simulator ilə işlədir. Qəbul/reddetmə, AI, Sentinel, hesabat və canlı yayım Main bazasında qalır.
- `backend/alembic/versions/0009_unified_device_history.py` və `backend/scripts/merge_device_history.py` köhnə Device run/göndəriş/audit tarixçəsini bir Main bazasına idempotent köçürür. Əvvəlki Device bazası silinmir.
- `frontend/src/App.tsx`, `frontend/src/pages/LoginPage.tsx`, `frontend/src/pages/VirtualDevicePage.tsx`, `frontend/src/lib/AuthContext.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/useVirtualDeviceTelemetry.ts` və `frontend/vite.config.ts` bir UI, rol əsaslı menyu, eyni origin API və WebSocket istifadə edir. Mission Control-un köhnə 5174 keçidi silindi.
- `start-orbitra.ps1`, `RUN-ORBITRA.cmd`, `START_HERE.md`, `docs/DEPLOY.md` bir lokal başlatma və bir domenə yerləşdirmə qaydasını verir.

## Qorunan məlumat

Birləşmədən əvvəl əsas bazada 14 run, 367 qəbul edilmiş nümunə və 5 təhlükəsizlik hadisəsi vardı. Köhnə Device bazasından 14 run metadatası, 936 göndəriş cəhdi və 54 audit qeydi əsas bazanın ayrıca tarixçə cədvəllərinə köçürüldü. Hesabat API-si 14 run üçün oxunur. Testlər əsas bazanın nüsxəsində aparıldı; orijinal baza sıfırlanmadı.

## Yoxlama

- Backend: `python -m unittest discover -s tests -q` — 27 test keçdi.
- Frontend: `npm run build` və `node --test tests/*.test.mjs` — build və 5 test keçdi.
- Birləşdirilmiş backend statik frontend-i tək URL-dən təqdim edərkən real HTTP/WebSocket smoke keçdi: giriş, rol qadağaları, eyni temperatur, pause/resume/reset, imza rəddi, Security hadisəsi, logout.
- Vite lokal proxy HTTP girişini, `/api` marşrutunu və WebSocket-i ötürdü.

## Qalan məhdudiyyətlər

Konkret hosting xidməti verilmədiyi üçün domenə faktiki deploy edilməyib. SQLite ilə bir proses/bir worker və daimi volume tələb olunur. Simulatorun aktiv RAM vəziyyəti server yenidən başlayanda davam etmir; tarixi run və hesabat məlumatı bazada qalır. AI ilk qiymətləndirmə üçün qəbul edilmiş nümunə pəncərəsi gözləyir. Bu, tədris üçün virtual sınaqdır.
