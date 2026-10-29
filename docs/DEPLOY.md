# ORBITRA-nı bir domenə yerləşdirmək

Bu təlimat xidmət seçmir və hazır deployment iddia etmir. **Bir instansiya** FastAPI servisi yığılmış React fayllarını, `/api/v1/*` və WebSocket-i eyni HTTPS domenindən təqdim edir. Vite yalnız lokal inkişaf üçündür.

1. Python 3.11+, Node.js 20+ və npm olan host seçin. Host **yenidən başladıqdan sonra silinməyən disk/volume** verməlidir. SQLite üçün eyni bazanı bir neçə replica paylaşmayın; backend-i bir worker və bir instansiya ilə işlədin.
2. `backend/orbitra.db`-ni daimi volume-a köçürün və `DATABASE_URL=sqlite:////data/orbitra.db` kimi tam yolla göstərin. `/data` misaldır; öz volume yolunuzu yazın. Köçürmədən əvvəl mövcud bazanın ehtiyatını alın. Köhnə Device DB tarixçəsi üçün `python -m scripts.merge_device_history /path/to/orbitra_device.db` əmrini bir dəfə işlədin.
3. HTTPS domeninizi və cookie ayarlarını konfiqurasiya edin. Aşağıdakı `example.com` yerinə öz domeninizi yazın; `.env`-ə real telemetriya açarı yazın, onu repoya daxil etməyin. `FRONTEND_ORIGIN` son slash olmadan dəqiq HTTPS origin olmalıdır. `TELEMETRY_HMAC_KEY` üçün `python -c "import secrets; print(secrets.token_hex(32))"` istifadə edin. `DEMO_LOCAL_ONLY=false` yalnız demo şifrələri dəyişdirildikdən sonra qoyulsun.

```text
DATABASE_URL=sqlite:////data/orbitra.db
FRONTEND_ORIGIN=https://example.com
COOKIE_SECURE=true
DEMO_LOCAL_ONLY=false
TELEMETRY_HMAC_KEY=<öz 64 hex simvollu açarınız>
```

4. Frontend-i yığın: `cd frontend && npm ci && npm run build`. Yığılmış `frontend/dist` backend tərəfindən `/login`, `/mission-control`, `/virtual-device` və `/assets` yollarında təqdim olunur. `VITE_API_BASE_URL` təyin etməyin; sorğular eyni origin-də `/api/v1`-ə gedir, WebSocket avtomatik `wss://example.com/api/v1/telemetry/ws` və `/api/v1/virtual-device/ws` olur.
5. Backend-i quraşdırın və migrasiya edin: `cd backend && python -m pip install -r requirements.txt && python -m alembic upgrade head`. Şifrələri `python -m scripts.manage_users change admin` və `python -m scripts.manage_users change virtual` ilə uzun, fərqli şifrələrə dəyişin. Yeni boş bazada `... manage_users init` istifadə edin. Şifrə terminalda gizli soruşulur, bazada yalnız hash saxlanır. Başlanğıc şifrəsini mühit dəyişəni ilə təyin etmək də mümkündür (`ORBITRA_ADMIN_INITIAL_PASSWORD`, `ORBITRA_VIRTUAL_INITIAL_PASSWORD`); bu yalnız hesab yoxdursa təsir edir, mövcud şifrəni dəyişmir. Mühit dəyişənini ilk quruluşdan sonra silin.
6. Bir backend prosesi başladın: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`. Hosting `PORT` verirsə həmin portu işlədin. Reverse proxy HTTPS-dən bu porta yönlənsin, `/api/v1/telemetry/ws` və `/api/v1/virtual-device/ws` üçün WebSocket `Upgrade`/`Connection` başlıqlarını ötürsün. Proxy `X-Forwarded-Proto` və host-u saxlasın. Tətbiq origin yoxlamasını `FRONTEND_ORIGIN` ilə aparır.
7. Domenin `/login` ünvanını, hər iki rolun məhdudiyyətlərini və WebSocket-i yoxlayın. Adi pəncərə və gizli pəncərə iki müstəqil cookie saxlayır; hər iki hesab eyni bazanın cari run məlumatını görür.

**Məhdudiyyət:** SQLite bir instansiya və daimi disk tələb edir. Replica və ya horizontal scaling üçün ayrıca PostgreSQL uyğunlaşdırması lazımdır; hazır kodun SQLite-ə məxsus sorğularını dəyişmədən çoxsaylı instansiya başladılmamalıdır. Simulator proses yenidən başlayanda aktiv sessiyanı davam etdirmir; tarixçə, hesabat və təhlükəsizlik qeydləri bazada qalır. Süni sınaqlar real raket və ya kiberhücum atributu deyil.
