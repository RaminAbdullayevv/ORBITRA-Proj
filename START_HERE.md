# ORBITRA: bir giriş, bir sistem

Bu layihənin **bir frontend-i, bir backend-i və bir əsas SQLite bazası** var. Virtual Device və Mission Control eyni backend-in eyni sınaq məlumatını görür. İctimai qeydiyyat yoxdur.

## Windows-da lokal başlatma

Python 3.11+, Node.js 20+ və npm lazımdır. İlk quraşdırma üçün internet lazım ola bilər. Əvvəlki iki tətbiqli `RUN-ORBITRA.cmd` pəncərəsini bağlayın ki, 8000 və 5173 portları boşalsın. Sonra bu qovluqdakı `RUN-ORBITRA.cmd` faylını iki dəfə klikləyin və pəncərəni açıq saxlayın. Yaxud PowerShell-də:

```powershell
# ZIP-dən çıxarılmış layihə qovluğunda PowerShell açın.
powershell -ExecutionPolicy Bypass -File .\start-orbitra.ps1
```

Skript yalnız `backend` və `frontend` xidmətlərini başladır, `backend/orbitra.db` bazasına Alembic migrasiyalarını tətbiq edir və köhnə Device bazası varsa onun run/göndəriş/audit tarixçəsini idempotent şəkildə Main bazasına köçürür. Mövcud telemetriya və hesabat qeydlərini sıfırlamır. Yeni boş bazada şifrələri terminalda gizli şəkildə daxil etməyi istəyir: lokal demo üçün admin hesabına `admin`, virtual hesabına `virtual` yazın. Mövcud hesab şifrələrini skript dəyişmir.

| Nə | Ünvan |
| --- | --- |
| Giriş | http://localhost:5173/login |
| Backend API | http://127.0.0.1:8000/api/v1/health |
| Monitorinq hesabı | `admin / admin` — yalnız lokal demo |
| Virtual cihaz hesabı | `virtual / virtual` — yalnız lokal demo |

`virtual` birbaşa `/virtual-device` ekranına, `admin` isə `/mission-control` ekranına yönləndirilir. Hesablar bir domenin eyni sessiya kukisindən istifadə edir. Bir brauzer profilində eyni anda yalnız bir hesab daxil ola bilər; yanaşı təqdimat üçün birini adi pəncərədə, o birini gizli pəncərədə və ya başqa profildə açın.

Yeni **Kiberhücum simulyasiyası** seçimi və üç virtual testin yoxlama addımları [docs/CYBER_DEMO.md](docs/CYBER_DEMO.md) sənədindədir.

## Əllə başlatma

İlk quruluşda `start-orbitra.ps1`-i bir dəfə işlədin. Sonrakı başlatmalarda iki PowerShell pəncərəsində:

```powershell
# Birinci PowerShell: layihə qovluğundan
cd .\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
# İkinci PowerShell: layihə qovluğundan
cd .\frontend
npm run dev
```

Lokal inkişafda Vite `/api` və WebSocket sorğularını 8000 portuna ötürür. Browser yalnız 5173 ünvanından istifadə edir. Bir prosesli yığılmış versiyanı yoxlamaq üçün Vite-ni dayandırın, `frontend` qovluğunda `npm run build` işlədin, sonra ayrıca PowerShell-də:

```powershell
cd .\backend
$env:FRONTEND_ORIGIN='http://127.0.0.1:8000'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Bu halda tək giriş `http://127.0.0.1:8000/login` olur. `FRONTEND_ORIGIN` brauzerin açdığı origin ilə tam eyni olmalıdır.

## Hesab və şifrə

Şifrələr SQLite-də Argon2 hash şəklində saxlanır. Kodda düz mətn şifrə yoxdur. Yeni hesablar üçün `python -m scripts.manage_users init`, mövcud şifrəni dəyişmək üçün `python -m scripts.manage_users change admin` və ya `... change virtual` əmrlərini backend qovluğunda işlədin. Əmrlər şifrəni ekranda göstərmədən soruşur; dəyişiklik aktiv sessiyaları ləğv edir. Yeni şifrə ən azı 12 simvol olmalıdır. **İctimai domenə çıxarmazdan əvvəl hər iki demo şifrəsini dəyişin.**

## Domen və daimi baza

[docs/DEPLOY.md](docs/DEPLOY.md) sənədində eyni domen, HTTPS, WebSocket reverse proxy, daimi disk və deploy əmrləri var. Konkret hosting seçilmədiyi üçün bu layihə heç bir hostinqə yerləşdirilməyib.

## Problem olduqda

1. Köhnə dörd prosesli başlatma pəncərəsini bağlayın; 8000 və 5173 portlarının boşaldığını yoxlayın.
2. `http://127.0.0.1:8000/api/v1/health` `{"status":"ok","database":"connected"}` qaytarmalıdır.
3. `backend/.env` içində 64 hex simvollu `TELEMETRY_HMAC_KEY` olmalıdır. `python -m scripts.setup_security` açar yoxdursa yaradır.
4. `backend` qovluğunda `python -m alembic upgrade head`, `frontend` qovluğunda `npm run build` işlədin və xəta mətnini yoxlayın.
5. Giriş işləmirsə `python -m scripts.manage_users change admin` və ya `change virtual` ilə şifrəni yeniləyin. Lokal demo şifrəsini ictimai hostda saxlamayın.
