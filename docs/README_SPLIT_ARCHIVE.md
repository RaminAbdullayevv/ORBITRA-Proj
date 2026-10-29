> İki tətbiqli hazır quruluşun başlatma təlimatı: [START_HERE.md](START_HERE.md). Aşağıdakı mətn orijinal layihə mərhələlərinin sənədidir.

# ORBITRA — Raket Sistemləri üçün Ağıllı Telemetriya və Virtual Sınaq Platforması

**Raket sistemlərini fiziki risk olmadan sına, izlə və qoru.**

ORBITRA raketin bort elektronikasını, sensorlarını, telemetriya və enerji sistemlərini virtual mühitdə simulyasiya edən ağıllı sınaq platformasıdır. Sistem canlı telemetriyanı izləyir, nasazlıqları aşkarlayır, məlumat bütövlüyünü yoxlayır və avtomatik sınaq hesabatı hazırlayır.

Bu lokal tədris platforması fiziki aparatla kalibrasiya edilməyib. Paketlər, rəqəmlər və qərarlar virtual sınağa aiddir.

## Məqsəd və arxitektura

```text
Virtual raket bort sistemləri (Python, 1 Hz)
  → imzalı telemetriya → qəbul qapısı / Sentinel
       ├─ qəbul edilmiş nümunə → SQLite → WebSocket → Missiya İdarəetmə / Rəqəmsal Model
       │                                      └─ Qayda mühərriki + lokal AI
       └─ rədd edilmiş nümunə → karantin + təhlükəsizlik insidenti + audit
  → sessiyaya bağlı Missiya Hesabatı → A4 PDF çapı
```

Frontend React/Vite, backend FastAPI, məlumat bazası SQLite və Alembic migrasiyalarıdır. Simulyasiya vaxtı, 11 sensor, ssenari gedişi və əmrlər backend-də hesablanır. Frontend yalnız serverin qəbul etdiyi, saxladığı nümunələri göstərir. WebSocket kəsildikdə tarixçə HTTP ilə tamamlanır. Aktiv məlumat köhnələrsə canlı kimi göstərilmir. API marşrutları və texniki enumlar sabit saxlanır; Azərbaycan dili üçün görünən etiketlər frontend-də xəritələnir.

## İş sahələri

1. **Missiya İdarəetmə:** canlı qrafiklər, sistem vəziyyəti, xəbərdarlıqlar, hadisələr və Sınağa hazırlıq.
2. **Virtual Raket Sistemi:** ssenari və Start/Pause/Resume/Reset idarəsi, 11 sensor, 2D raket sxemi.
3. **AI Analizi və Xəbərdarlıqlar:** normal baza ilə müqayisə, anomaliya balı, sensor və izah.
4. **Təhlükəsizlik Mərkəzi:** rədd edilən paketlər, insidentlər, audit.
5. **Rəqəmsal Model:** yalnız qəbul edilmiş telemetriyadan altı sistem blokunun vəziyyəti.
6. **Missiya Hesabatı:** bir sessiyanın saxlanmış nəticələri və PDF kimi çap.
7. **Telemetriya Etibarlılığı:** Sentinel mərhələləri, sübutlar, karantin və qərar tarixçəsi.

### Raket sxemi

SVG sxemində sensor bloku, bort kompüteri, telemetriya və rabitə, enerji, istilik və virtual faydalı yük üçün altı əlaqə xətti və məlumat kartı var. Rənglər qəbul edilmiş son telemetriya və Sentinel qərarından çıxarılır: yaşıl normal, sarı xəbərdarlıq, qırmızı kritik, boz etibarlı cari məlumat yoxdur. Sensor 1 digər iki temperatur kanalı ilə uyğun gəlmədikdə ayrıca sensor xəbərdarlığı görünür; təcrid olunmuş ölçmə bütün istilik sistemini kritik etmir. Virtual faydalı yük CPU yükü ilə təmsil olunan tədris göstəricisidir.

### Sınağa hazırlıq

Bu göstərici canlı backend məlumatından frontend-də hesablanır; real buraxılış və uçuş qərarı deyil. Sessiya və qəbul edilmiş nümunə yoxdursa **MƏLUMAT YOXDUR**. Qəbul axını kəsilibsə, kritik qayda və ya əsas sistem problemi, yaxud kritik bütövlük/karantin hadisəsi varsa **HAZIR DEYİL**. Qeyri-kritik sistem/Sentinel xəbərdarlığı və ya dayandırılmış sınaq varsa **DİQQƏT**. Bağlantı aktiv, etibarlı telemetriya var və əsas bloklar normaldırsa **HAZIR**. Kart səbəbi də göstərir. Hesabatda həmin sessiyanın saxlanmış nəticələrinə əsaslanan retrospektiv hazırlıq göstərilir.

## Başlatma (Windows PowerShell)

Lazım olanlar: Python 3.11+, Node.js 20+ və npm/pnpm. İlk asılılıq quraşdırması internet tələb edə bilər. Bundan sonra model artifact-i, SQLite, API və WebSocket yalnız lokal işləyir.

Backend üçün ayrıca terminal:

```powershell
cd C:\Users\ramin\Documents\Codex\2026-09-24\files-pasted-by-the-user-s\outputs\orbitra\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m scripts.setup_security
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Mövcud quraşdırmada `.venv` və `.env` fayllarını təkrar yaratmayın; `python -m alembic upgrade head` mövcud qeydləri saxlayır. `setup_security` yalnız yoxdursa lokal HMAC açarı və admin hesabı yaradır, mövcud admin şifrəsini dəyişmir. SQLite faylı `backend/orbitra.db` yerində qalır.

Frontend üçün ikinci terminal:

```powershell
cd C:\Users\ramin\Documents\Codex\2026-09-24\files-pasted-by-the-user-s\outputs\orbitra\frontend
pnpm install --offline
pnpm run dev
```

İlk quraşdırmada offline paket keşiniz yoxdursa `pnpm install` (və ya `npm install`) istifadə edin. Mövcud `node_modules` ilə yenidən quraşdırmaya ehtiyac yoxdur. Login: [http://localhost:5173/login](http://localhost:5173/login). API sənədi: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

**Lokal demo girişi: `admin / admin`.** Şifrə backend-də Argon2 hash kimi saxlanır, frontend koduna yerləşdirilmir. Bu hesabı yalnız localhost təqdimatı üçün istifadə edin. Backend admin girişini loopback müştəri ilə məhdudlaşdırır. Köhnə operator, analitik və müşahidəçi hesabları varsa silinmir; təqdimat üçün admin kifayətdir.

## Demo ssenariləri

| Görünən ad | Texniki ssenari | Gözlənilən nəticə |
| --- | --- | --- |
| Normal raket sistemi sınağı | `NORMAL_MISSION` | Normal qəbul edilmiş telemetriya |
| Bort sistemində temperatur anomaliyası | `TEMPERATURE_ANOMALY` | Əlaqəli istilik və yük artımı; qayda, AI və Sentinel nəticələri |
| Temperatur sensorunda nasazlıq | `SINGLE_SENSOR_FAULT` | Sensor 1 fərqlənir; ayrıca sensor xəbərdarlığı |
| Etibarsız telemetriya paketi | `INVALID_TELEMETRY` | Format rəddi; #10 paket karantində, qrafik və AI girişində yoxdur |
| Yanlış imzalı telemetriya paketi | `INVALID_SIGNATURE` | İmza rəddi və təhlükəsizlik insidenti |
| Təkrar göndərilmiş telemetriya paketi | `REPLAYED_TELEMETRY` | Təkrar paket rəddi və karantin |

Başqa ssenari seçmək üçün cari sessiyanı bitirin və ya sıfırlayın; yeni Başlat ayrıca `run_id` yaradır. Dayandır və Davam etdir eyni sessiyanı saxlayır. Virtual yükü azalt əmri yalnız işləyən sessiyada bir dəfə qəbul edilir və sonrakı ölçmələrə tədricən təsir edir.

**Qayda mühərriki** qəbul edilmiş ölçmələrin hədlərini yoxlayır. **AI** 20 ardıcıl qəbul edilmiş nümunənin davranışını lokal öyrənilmiş normal baza ilə müqayisə edir; bal ehtimal və ya əminlik faizi deyil. **Sentinel** formatı, mənbəni, HMAC imzasını, sıra/vaxtı və sensor uyğunluğunu yoxlayır. Rədd edilmiş paket AI, qrafik və Rəqəmsal Modelə daxil olmur. Heç bir modul real aparata əmr göndərmir.

## Testlər

```powershell
cd C:\Users\ramin\Documents\Codex\2026-09-24\files-pasted-by-the-user-s\outputs\orbitra\backend
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests -v
```

```powershell
cd C:\Users\ramin\Documents\Codex\2026-09-24\files-pasted-by-the-user-s\outputs\orbitra\frontend
node --test tests/*.test.mjs
pnpm run typecheck
pnpm run build
```

## Məlum məhdudiyyətlər

- Sensorlar sintetikdir; rəqəmlər və hədlər real raket üçün kalibrasiya edilməyib.
- Bir aktiv lokal cihaz/sessiya işləyir. Server yenidən başlayanda aktiv sessiya davam etdirilmir; saxlanmış tarixçə qalır.
- AI ilk qiymətləndirmə üçün 20 ardıcıl qəbul edilmiş nümunə gözləyir.
- Sınağa hazırlıq və Sentinel səbəb izahı tədris qərarıdır, fiziki nasazlıq və ya hücumun təsdiqi deyil.
- Hesabat əvvəlki canlı bağlantı fasilələrini ayrıca ölçmür; saxlanmış sıra boşluqlarını göstərir.
