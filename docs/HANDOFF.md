# ORBITRA təhvil qeydi — mərhələ 4

## Hazır vəziyyət

- React/Vite interfeysində altı birbaşa açılan route və klaviatura ilə işləyən menyu var. Virtual Device və Mission Control canlı backend telemetriyasını göstərir; digər dörd bölmə boş vəziyyətini dürüst izah edir.
- Frontend açılışda və hər 5 saniyədə `/api/v1/health` sorğusu göndərir. Backend və SQLite cavab verəndə bağlantı, cavab verməyəndə izahlı əlaqə xətası göstərilir.
- FastAPI əvvəlki health və app-info endpoint-lərini, həmçinin Virtual Device üçün bir GET və dörd POST endpoint-ini təqdim edir. İlkin Alembic migrasiyası dəyişməyib; simulator yaddaşdadır.
- `.env.example` faylları lokal ünvanları göstərir. Lokal `.env`, SQLite bazası, virtual mühit, `node_modules` və build çıxışı Git tərəfindən nəzərə alınmır.

## Mərhələ 1-dən qorunan nəticə

- Python asılılıqları virtual mühitə quruldu; `python -m alembic upgrade head` `0001_initial` reviziyasını tətbiq etdi.
- Uvicorn işə düşdü; health `{"status":"ok","database":"connected"}`, app-info isə ad, mərhələ və `simulation_only` qaytardı.
- Frontend paketləri pnpm ilə quruldu; TypeScript yoxlaması və production build uğurlu oldu. Lokal `npm` qısayolu bu test kompüterində düzgün quraşdırılmadığı üçün yoxlama pnpm ilə aparıldı.
- Vite işə düşdü; altı route brauzerdə birbaşa URL ilə açıldı. Menyu klik və Enter ilə keçdi, fokus vəziyyəti göründü.
- Backend dayandırılanda əlaqə xətası və işə salma ipucu göründü. Backend yenidən başlayanda status avtomatik bərpa olundu.
- 1440×900 və 1920×1080 ölçülərində məzmunun üfüqi daşması yoxlandı; 1920×1080 vizual baxışdan keçdi.
- CORS `http://localhost:5173` üçün cavab verdi; başqa origin üçün icazə başlığı qaytarmadı.

## Mərhələ 2 yoxlaması

- `python -m unittest discover -s tests -v`: Start → Pause → Resume → Reset, yersiz əməliyyatlar, sabit seed və tədrici sintetik dəyərlər keçdi.
- Canlı API sınağında IDLE → RUNNING → PAUSED → RUNNING → IDLE keçidləri, pause dondurması, eyni `run_id` ilə resume və yersiz pause üçün HTTP 409 görüldü.
- Brauzerdə Virtual Device başlanğıc göstəriciləri, 11 sensor, düymələrin vəziyyətə görə aktivliyi, Start/Pause/Resume/Reset, səhifə yenilənəndə PAUSED vəziyyətin qayıtması və API ilə eyni dəyərlər yoxlandı.
- Backend dayandırılanda son göstəricilər gizlədildi və əlaqə xətası göstərildi; yenidən başlayanda cihaz IDLE vəziyyətində bərpa olundu.
- Altı route yenidən açıldı; menyu klik və Enter ilə işləyir. TypeScript yoxlaması və production build keçdi. Health və app-info cavabları, Alembic `0001_initial (head)` reviziyası və SQLite-də yalnız `alembic_version` cədvəli yoxlandı.

## Mərhələ 3 nəticəsi

- `0002_telemetry` migrasiyası sessiya və telemetriya cədvəllərini yaratdı. Bir simulatorun hər saniyəlik vəziyyəti commit-dən sonra WS ilə yayımlanır; `(run_id, sequence_number)` unikaldır.
- Virtual Device və Mission Control `useLiveTelemetry` qatından eyni run-un saxlanmış nümunələrini göstərir. İkinci səhifədə temperatur, batareya, cərəyan və üç rabitə göstəricisi üçün vahidli qrafiklər var.
- Start/Pause/Resume/Reset status hadisələri hər iki açıq səhifəyə ötürülür. Səhifə yenilənəndə tarixçə bərpa olunur; WS bağlantısı qayıdanda son sıra nömrəsindən sonrakı boşluq HTTP ilə tamamlanır. Bağlantı itkisi və köhnəlmiş məlumat canlı kimi göstərilmir.
- Mərhələ 4 Mission Control-un əlavə operator funksiyalarını bu telemetriya və status qatına bağlamalıdır; ayrıca sensor generatoru yaratmamalıdır.

## Mərhələ 3 yoxlaması

- `python -m alembic upgrade head` və `python -m alembic current`: `0002_telemetry (head)`.
- `python -m unittest discover -s tests -v`: 3 test keçdi; Start → Pause → Resume → Reset, eyni run-un davamı, yeni run-un ayrılması və təkrar nümunənin bazada rədd edilməsi yoxlandı.
- `pnpm run typecheck` və `pnpm run build`: TypeScript və Vite production build keçdi. Lokal `npm` qısayolu nasazdır, ona görə mövcud pnpm istifadə edildi.
- Brauzerdə iki səhifə eyni PAUSED run `bb60cfe1-ec33-4aa6-a0ed-814036ddc960` üçün sıra `474` və Temperatur 1 `21.46 °C` göstərdi. SQLite həmin run üçün 1–474 arası 474 fərqli sıra saxladı; uzun pause zamanı say artmadı. Mission Control yenilənəndə eyni vəziyyət və altı qrafik qayıtdı.
- Resume eyni run-u davam etdirdi; Reset hər iki ekranı IDLE etdi və qrafikləri təmizlədi; yeni Start `eaaf45ea-1d42-4f1c-8211-ae0071fbdf5a` run-unu yaratdı.
- Yeni run-un ilk 75 nümunəsi 1–75 ardıcıl və 75 fərqli sıra ilə təxminən 74 saniyədə saxlandı; ilk 30 saniyənin hər biri üçün bir qeyd var. Köhnə run-un 482 qeydi Reset-dən sonra qaldı və yeni run-a qarışmadı.
- Canlı WS müştərisi ayrılıb 3,4 saniyə sonra qayıdanda `after_sequence=63` ilə 64, 65, 66 nümunələrini HTTP tarixçəsindən təkrarsız tamamladı.
- Backend söndükdə Virtual Device rəqəmləri gizlətdi, Mission Control altı qrafiki tarixi kimi işarələdi. Backend yenidən başlayanda hər ikisi avtomatik IDLE-a qayıtdı; əvvəlki run `INTERRUPTED` statusu və tarixçəsi ilə HTTP-dən oxundu.
- `/api/v1/health`, `/api/v1/app-info`, aktiv və tarixi telemetriya vəziyyəti HTTP 200 qaytardı. `/ai-alerts`, `/security`, `/digital-twin`, `/mission-report` brauzerdə başlıqları ilə açıldı.

Məhdudiyyət: bir backend prosesi və bir aktiv lokal cihaz dəstəklənir; proses yenidən başlayanda yaddaşdakı aktiv simulyasiya davam etdirilmir. Qrafik yalnız son beş dəqiqəni göstərir, bazadakı tam tarixçə qalır.

## Mərhələ 4 nəticəsi

- Mövcud simulator `ENDED` terminal vəziyyətini və hər run-da bir dəfə lokal virtual yük azaltmanı dəstəkləyir. CPU hədəfi 28%-dən 20%-ə dəyişir; cərəyan və temperatur sonrakı nümunələrdə modelə uyğun tədricən dəyişir.
- `0003_operator_events` migrasiyası qəbul və rədd edilmiş əməliyyatların event_id, run_id, vaxt, simulyasiya vaxtı, əvvəl/sonra status, nəticə, səbəb və `local_demo_operator` mənbə etiketini saxlayır. Bu etiket autentifikasiya deyil.
- Mission Control status, beş operator düyməsi, yeddi sensor qrafiki, dörd tədris sağlamlıq bloku, backend-dən təsdiqlənən xəbərdarlıq boş vəziyyəti və SQLite-dan yenilənən Timeline göstərir. Son beş hadisə dərhal görünür; tam tarixçə açıla bilir.
- `operator_event` WS mesajı mövcud `/api/v1/telemetry/ws` axınındadır. Frontend HTTP/WS hadisələrini event_id ilə ayırır və yenidən qoşulanda event_number kursorundan tarixçəni tamamlayır.

## Mərhələ 4 canlı yoxlaması

- `python -m alembic upgrade head`, `python -m alembic current`: `0003_operator_events (head)`.
- `python -m unittest discover -s tests -v`: 5 test keçdi; End-dən sonra Resume rəddi, yeni run, yük azalmasının tədrici təsiri və təkrar əməliyyatın yalnız bir uğurlu dəyişiklik yaratması yoxlandı.
- `pnpm run typecheck` və `pnpm run build` keçdi. `npm` qısayolu bu lokal kompüterdə nasazdır.
- İki brauzer səhifəsi run `3f7fe30c-85d7-4618-8f7e-0b85404219ef` üçün sıra 6 və Temperatur 1 `21.47 °C` göstərdi. Pause zamanı hər ikisi sıra 15 və 15 saniyədə dayandı; SQLite sayı artmadı. Səhifə yenilənəndə eyni run və iki hadisə geri gəldi.
- Resume eyni run-u davam etdirdi. Reduce-dən sonra CPU `28.87% → 20.37%`, cərəyan `1.90 A → 1.81 A`, Temperatur 1 `21.59 °C → 20.71 °C` dəyişdi. End hər iki ekranda eyni run-u ENDED və sıra 56 göstərdi; əlavə nümunə yaranmadı.
- End-dən sonra Resume, End və Reduce sorğuları HTTP 409 qaytardı. SQLite-də hər uğurlu əməliyyat üçün bir hadisə, üç rədd hadisəsi və ENDED run saxlandı. Yenilənmiş Timeline səkkiz fərqli event_id göstərdi. Yeni Start `5c0b4451-db84-4702-be57-c4b05a19d2be` run-u ilə boş qrafik və tək Start hadisəsi yaratdı; sonradan iki səhifə həmin run-un sıra 184 və `21.48 °C` dəyərində uyğunlaşdı.
- Backend söndükdə Mission Control əlaqə itkisini göstərdi, əməliyyatları deaktiv etdi və “xəbərdarlıq yoxdur” iddia etmədi; backend yenidən başlayanda hər iki səhifə IDLE-a qayıtdı. 1440×900 ölçüdə Mission Control-un yuxarı statusu, əməliyyatları, ilk qrafiki və sağlamlıq blokları vizual baxışdan keçdi.
- Ayrılmış WS müştərisi zamanı Pause əməliyyatı ediləndən sonra yenidən qoşulan müştəri PAUSED vəziyyətini və `after_id` API-si ilə çatışmayan tək `event_id` hadisəsini aldı; iki brauzer səhifəsi də həmin run-un PAUSED vəziyyətini və iki timeline hadisəsini göstərdi.

Bu paraqraf Mərhələ 4 sonundakı vəziyyəti təsvir edir; Mərhələ 5 nəticəsi aşağıdadır. Proses restartı aktiv simulyasiyanı davam etdirmir; tarixçə və hadisələr qalır.

## Mərhələ 5 nəticəsi və canlı yoxlama

- `0004_scenarios` migrasiyası tətbiq edildi. Run ilə ssenari, qayda xəbərdarlığının açılma/bərpa metadata-sı və formatı rədd edilmiş test nümunəsi SQLite-da saxlanır.
- `python -m unittest discover -s tests -v`: 8 test keçdi. Yeni testlər ssenarinin sabit sensor ardıcıllığını, ayrı run ID-ləri, temperatur yükü/cərəyan/istilik ardıcıllığını, Reduce-dən sonrakı bərpanı, #10 rəddini, normal WS `telemetry_sample` axınında #10-un olmamasını və sonrakı nümunələri yoxladı.
- `pnpm run typecheck` və `pnpm run build` keçdi. `git diff --check` keçdi (Windows CRLF bildirişləri var).
- İki açıq brauzer pəncərəsində Normal run `e2b59348-f7d2-4e4a-b7a1-523a39613cab` eyni ID və sensorlarla göründü. Pause/Resume/End işlədildi; Mission Control aktiv xəbərdarlıq göstərmədi.
- Temperature run `d500e874-86c2-4a15-951d-34ce2a47014c` zamanı CPU ~41.83%-ə yüksəldi, Temperatur 1 `24.88 °C` olanda qayda xəbərdarlığı açıldı. Reduce əməliyyatından sonra CPU ~22.47%-ə, istilik tədricən `22.35 °C`-ə endi; xəbərdarlıq bağlandı. Mission Timeline açılma, Reduce və bərpanı göstərdi; səhifə yenilənəndən sonra dörd hadisə bazadan qayıtdı.
- Invalid run `bc3e14d0-c090-448a-8d52-a0dc009c146a` üçün Security Operations #10, `schema_version=9.9-test`, səbəb, run ID və vaxtı göstərdi; səhifə yenilənəndən sonra eyni hadisə qayıtdı. Mission Control #10 qrafik boşluğunu və format hadisəsini göstərdi. Birbaşa SQLite sorğusunda qəbul edilmiş #10 sayı `0`, rədd qeydi `1`, qəbul edilmiş ardıcıllıq isə `8, 9, 11, 12` idi; sonrakı düzgün nümunələr davam etdi. Reset cihazı IDLE/0-a qaytardı; tarixi run-un rədd qeydi API-dən oxundu.

Məhdudiyyət: yalnız bir aktiv lokal cihaz və sintetik axın var; proses restartı run-u davam etdirmir. AI analizi, kriptoqrafik imza və rol yoxlaması bu mərhələyə daxil deyil. Mərhələ 6 üçün yalnız qəbul edilmiş `telemetry_samples` cədvəli analitik giriş olmalıdır.

## Mərhələ 6 nəticəsi və canlı yoxlama

- `0005_ai_analysis` migrasiyası model versiyası və davamlı AI hadisələrini saxlayır. Yalnız commit olunmuş `telemetry_samples` sətirlərindən 20 ardıcıl nümunəlik pəncərə qiymətləndirilir; model ssenari adını almır. Model faylı və kalibrasiya metadata-sı layihənin etibarlı `backend/model_artifacts` qovluğundadır.
- Təlim `python -m scripts.train_ai` ilə ayrı normal sessiyalarda və sabit seed-lərlə aparıldı. Skript ikinci dəfə işə salınanda model artifact-inin SHA-256 dəyəri eyni qaldı. Ayrı yekun sınaqda dörd temperatur hadisəsinin 4-ü tapıldı, buraxılan 0, səkkiz normal sessiyada yanlış AI xəbərdarlığı 0 oldu. Başlanğıcdan xəbərdarlığa qədər vaxt hər dörd hadisədə 14 saniyə idi. Bu yalnız sintetik simulator nəticəsidir.
- `python -m unittest discover -s tests -v`: 13 test keçdi. `pnpm run typecheck`, `pnpm run build`, `git diff --check` keçdi. `python -m alembic current`: `0005_ai_analysis (head)`.
- Canlı Normal run `b2236281-f74a-4d87-840c-ace2fcf9e3d4` 68 qəbul edilmiş nümunə ilə bitdi; 20-ci nümunədən sonra AI balı göstərildi, davamlı AI hadisəsi açılmadı.
- Canlı Temperature run `743eb412-99f5-4fcc-80cc-8a62fe0d3bd1` zamanı qayda xəbərdarlığı və AI hadisəsi ayrı göstərildi. AI hadisəsi #22-də açıldı (`event_id=1abbe4a3-3f48-4d0c-874f-1e53dea87521`), Mission Control keçidi həmin hadisənin izahına apardı. Reduce əməliyyatından sonra yeni nümunələr qiymətləndirildi, qayda və AI hadisələri bərpa olundu. Səhifə yenilənəndə eyni event_id, bal, sensorlar, başlanma və bitmə vaxtları SQLite-dan qayıtdı.
- PAUSED vəziyyətində qəbul edilmiş sıra #65 və son AI qiymətləndirməsi #65 olaraq sabit qaldı; Resume eyni run-da davam etdi. Canlı Invalid run `47bb1058-7d54-4d0d-abf1-349248cbbc3e` üçün #10 qəbul edilmiş nümunələrdə yox idi, Security Operations-da bir format rəddi qaldı və AI hadisəsi yaranmadı. Model yalnız #11-dən başlayan yeni ardıcıl pəncərədən sonra bal göstərdi.
- Backend yenidən başladıldıqda model `READY`/`iforest-normal-v1` kimi yükləndi; əvvəlki Temperature hadisəsi tarixi `/api/v1/telemetry/runs/{run_id}/ai-events` endpoint-indən eyni event_id və `RESOLVED` vəziyyəti ilə oxundu. Aktiv simulyasiya restartdan sonra IDLE-dır; tarixi run və hadisələr SQLite-da qalır.

## Mərhələ 7 nəticəsi

- `0006_security` tətbiq edildi. Mövcud SQLite-da 1552 qəbul edilmiş telemetriya sətri, 1 AI hadisəsi və 3 köhnə rədd qeydi saxlandı; üç köhnə rədd ayrıca tarixi insidentə köçürüldü. Köhnə qəbul edilmiş nümunələrin imzası geriyə dönük təsdiqlənə bilmir.
- Lokal hesab qurulması `python -m scripts.setup_security` ilə interaktivdir. Hazır parol kodda yoxdur; Argon2 hash, 8 saatlıq server sessiyası, `HttpOnly` cookie, giriş cəhdi limiti, Origin/CSRF və WS origin/session yoxlamaları əlavə edildi.
- Operator cihaz və ssenarini idarə edir; Analyst yalnız insidentə qeyd/bağlama qərarı verir; Observer oxuyur. Server rolu hər mutasiya zamanı yoxlayır. Yeni operator hadisəsi autentifikasiya olunmuş `user_id` saxlayır.
- Simulatorun HMAC-SHA256 imzası schema, run, source, sıra, vaxt, status və sensorları əhatə edir. Schema, imza, mənbə və təkrar səbəbləri ayrıca audit/insident kodları alır. Rədd edilmiş nümunə adi telemetriya, qayda və AI-yə keçmir.
- Security Operations son 200 audit və insidenti göstərir; Analyst qeydi və səbəbli bağlama SQLite-da qalır. Köhnə `rejected_telemetry` unikal indeksi təkrar eyni sıranın ikinci rədd sətrini saxlamaya bilər, amma hər cəhdin audit və insidenti yazılır. Bu lokal sintetik təhlükəsizlik nümayişidir.
- İnteraktiv hesab qurulması ayrıca müvəqqəti SQLite bazasında terminaldan üç gizli parol və təsdiqlə sınaqdan keçdi. Brauzerdə Operator Normal Start/Pause/Resume/End etdi; Invalid run-da #10 `SCHEMA_REJECTED` insidenti yarandı və #11-dən sonrakı axın davam etdi. Observer tarixçəni oxudu, idarəetmə bağlı idi. Analyst insidentə qeyd yazıb səbəblə bağladı; müəllif, vaxt və hər iki audit hadisəsi ekranda göründü. Bu canlı test məlumatları əsas `backend/orbitra.db` bazasına yazılmadı.
- Əsas baza `0006_security (head)` və health `ok` ilə yenidən açıldı. Miqrasiya sonrası 1552 telemetriya, 1 AI hadisəsi, 3 köhnə rədd və 3 tarixi insident saxlanır. Əsas bazada istifadəçi hələ yoxdur; sahibi `python -m scripts.setup_security` ilə öz parollarını təyin etməlidir.
