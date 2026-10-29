# ORBITRA Sentinel — texniki qeyd

Sentinel lokal virtual raket telemetriyasının qəbul sərhədidir. Fiziki aparat və real şəbəkə təhlükəsizliyi zəmanəti deyil.

## Məlumat sərhədi

Simulator saniyədə bir sintetik raket sistemi telemetriyası nümunəsi yaradır. `SignedTelemetryPacket` HMAC-SHA256 imzası, cihaz və paket ID-si ilə `TelemetryStore.process_sample` yoluna daxil olur. Qapı format, tanınmış mənbə, imza, artan sıra və UTC vaxt pəncərəsini yoxlayır. Qapıdan keçməyən paket `rejected_telemetry`, `telemetry_trust_assessments`, `security_incidents` və auditdə saxlanır; qəbul edilmiş `telemetry_samples`, qrafik, Rəqəmsal Model və AI girişinə keçmir.

Qəbul edilmiş nümunələrdə Sentinel sensor uyğunluğu və sadələşdirilmiş Rəqəmsal Model müqayisəsi aparır. Qayda mühərriki temperatur/paket itkisi hədlərini, AI isə 20 ardıcıl qəbul edilmiş nümunənin normal bazadan fərqini qiymətləndirir. Bunlar müstəqil mənbələrdir. `trust_assessment` mövcud telemetriya WebSocket axınında yayılır. Frontend qərarları ID ilə təkrarsız birləşdirir.

`0008_sentinel` migrasiyası etibarlılıq qərarları və karantin metadata-sını əlavə edir; əvvəlki SQLite qeydlərini silmir. `sentinel-teaching-v1` qaydası tək temperatur sensoru uyğunsuzluğunu əlaqəli sistem istiliyindən ayırır. Tək sensor xətası bütün istilik sistemini kritik etmir. Yekun texniki enumlar backend-də dəyişməz qalır, Azərbaycan dilində qarşılıqları frontend-də göstərilir.

## Təqdimat

[Giriş](http://localhost:5173/login) → `admin / admin` → **Missiya İdarəetmə** → **Virtual Raket Sistemi**. Normal ssenaridə canlı paket, Sınağa hazırlıq və altı bloklu sxemi göstərin. Temperatur anomaliyasında üç kanalın əlaqəli yüksəlişini, AI/Qayda/Sentinel fərqini və virtual yükü azaltma əmrini göstərin. Sensor nasazlığında sensor 1 ayrıca xəbərdarlıqdır. Yanlış imza və ya təkrar paket ssenarisində #10 paket karantinə düşür, etibarlı qrafik və AI girişinə daxil olmur. Sonda **Missiya Hesabatı** səhifəsini açın. Tam addımlar [demo ssenarisində](DEMO_SCRIPT_AZ.md) verilib.

## Lokal başlatma və test

Backend: `cd backend`; `.\.venv\Scripts\python.exe -m alembic upgrade head`; `.\.venv\Scripts\python.exe -m scripts.setup_security`; `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.

Frontend: `cd frontend`; `pnpm run dev`. Testlər: backend-də `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`; frontend-də `node --test tests/*.test.mjs`, `pnpm run typecheck`, `pnpm run build`. Asılılıqlar və model artifact-i qurulduqdan sonra iş lokal və internetsiz davam edir.
