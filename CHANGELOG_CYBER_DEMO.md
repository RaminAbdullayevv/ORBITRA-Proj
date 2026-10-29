# ORBITRA kibertəhlükəsizlik demosu — dəyişikliklər

## Mövcud vəziyyət

Vahid tətbiq saxlanıldı: `backend/`, `frontend/`, `backend/orbitra.db`. `admin` və `virtual` rolları eyni girişdən işləyir; HTTP API, WebSocket və serverin təqdim etdiyi səhifələr backend tərəfindən qorunur. Şifrələri interaktiv dəyişmək mexanizmi əvvəlcədən var idi, yenidən yazılmadı. Əvvəlki altı ssenari saxlanıldı; `SPOOFED_TELEMETRY` yeni əlavə edildi.

## Dəyişən fayllar

- `backend/app/simulator.py`, `backend/app/integrity.py`, yeni `backend/app/cyber_demo.py`: əvvəlcədən müəyyən edilmiş üç virtual test paketi və test niyyəti üçün metadata.
- `backend/app/telemetry.py`: test niyyətini faktiki format, mənbə, HMAC və sıra yoxlaması nəticəsindən ayrı saxlayır; rədd sübutu, Sentinel hadisəsi və aid olduğu blokun məlumat etibarlılığı eyni run-da görünür. Təkrar eyni rədd cəhdi əvvəlki kimi idempotent qalır.
- `backend/app/api/security_routes.py`: hadisənin göndərilən paketini, keçilən/uğursuz yoxlamaları, nəticəni və əsaslandırılmış MITRE oxşarlığını admin API-sində qaytarır.
- `backend/app/reports.py`: hər run üzrə virtual test hadisələrini saxlanmış Sentinel qərarlarından sayır və aşkarlanma faizini hesablayır.
- `frontend/src/components/ScenarioPicker.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/labels.ts`, `frontend/src/pages/VirtualDevicePage.tsx`: Kiberhücum simulyasiyası seçimi, üç test növü və About mənbələri.
- `frontend/src/pages/SecurityOperationsPage.tsx`, `frontend/src/pages/DigitalTwinPage.tsx`, `frontend/src/pages/MissionControlPage.tsx`, `frontend/src/pages/MissionReportPage.tsx` və əlaqəli CSS: hadisə izahı, operator xəbərdarlığı, fiziki haldan ayrı məlumat etibarlılığı işarəsi və hesablanmış hesabat nəticəsi.
- `backend/tests/test_unified_application.py`, yeni `backend/tests/cyber_http_smoke.py`: üç testin real backend axını, canlı HTTP/WebSocket və saydan hesablanan faiz üçün inteqrasiya sınaqları.
- `README.md`, `START_HERE.md`, yeni `docs/CYBER_DEMO.md`: istifadə və məhdudiyyətlər.

## Faktiki yoxlama

- Backend: `python -m unittest discover -s tests -q` — 29/29 keçdi.
- Frontend: `node --test tests/*.test.mjs` — 5/5 keçdi; `npm run build` uğurludur.
- Vahid server: lokal HTTP giriş, API rol qadağaları, WebSocket, eyni temperatur, rədd paketi və çıxış smoke testi keçdi.
- Vite proxy: lokal HTTP giriş, API/WebSocket və eyni temperatur smoke testi keçdi.
- Real backend prosesi və ayrıca müvəqqəti SQLite nüsxəsi ilə `backend/tests/cyber_http_smoke.py`: üç testin hər birində canlı WebSocket rəddi, Security detalı, Digital Twin etibarlılıq məlumatı və 1/1 hesabat nəticəsi keçdi; əsas baza dəyişdirilmədi.
- Yeni üç ssenarinin hər biri ayrıca run-da gözlənilən səbəblə rədd edildi; sıra 10 qrafikə düşmədi, Security hadisəsi və hesabatda 1/1 hesablanmış nəticə yarandı.

## Məhdudiyyətlər

Bunlar yalnız əvvəlcədən müəyyən edilmiş virtual paketlərdir; real hücumçunun kimliyi və ya niyyəti müəyyən edilmir. MITRE T1692.002 yalnız saxta mənbə testində nəzəri oxşarlıqdır; replay və integrity üçün dəqiq texnika təyin edilmir. Faiz yalnız nəticəsi saxlanmış virtual testlərdən hesablanır. Hər run-un öz hesabatı var; fərqli runların sayları qarışdırılmır. Simulatorun canlı RAM vəziyyəti backend yenidən başladıqda davam etmir, bazadakı tarixçə qalır. Konkret hostingə deployment edilməyib.
