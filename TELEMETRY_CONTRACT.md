# ORBITRA telemetriya müqaviləsi — vahid backend

Virtual simulator, telemetriya qapısı və canlı yayım eyni `backend` prosesindədir. Ayrı Device HTTP servisi artıq işə salınmır. Simulatorun imzalı nümunələri yenə də əvvəlki yoxlama qapısından keçir; qəbul edilənlər əsas SQLite bazasına, rədd edilənlər karantin və təhlükəsizlik hadisəsinə yazılır.

## Paket `schema_version = "1.0"`

Hər paketdə `packet_id` (UUID sübut identifikatoru), `source_id = "orbitra-local-simulator"`, `signature` (HMAC-SHA256 hex) və `snapshot` var. Snapshot sahələri: `schema_version`, `run_id` (UUID), `scenario`, `status`, `simulation_elapsed_seconds` (sıra nömrəsi), `updated_at` (UTC vaxtı), `system_mode`, `subsystem_statuses` və 11 sensor dəyəri (`battery_level_percent`, `voltage_v`, `current_a`, `temperature_1_c`, `temperature_2_c`, `temperature_3_c`, `cpu_load_percent`, `memory_usage_percent`, `signal_strength_percent`, `communication_latency_ms`, `packet_loss_percent`).

İmza `backend/app/integrity.py` faylının `canonical_bytes` funksiyasına əsasən hesablanır: schema versiyası, run ID, ssenari, source ID, sıra, vaxt, status və sensor dəyərləri sabit açar sıralaması ilə JSON-a çevrilir. `packet_id` ayrıca sübut identifikatorudur; məzmun imzasının tərkibinə daxil deyil. 32 baytlıq HMAC açarı `TELEMETRY_HMAC_KEY` konfiqurasiyasından oxunur, `.env.example`-da boş saxlanır. Boş və ya yanlış uzunluqlu açarla backend işə düşmür.

Qapı formatı, mənbəni, imzanı, run ID-ni, sıra təkrarını, vaxtın uyğunluğunu və sensor fərqini yoxlayır. `SCHEMA_REJECTED`, `INTEGRITY_REJECTED`, `REPLAY_REJECTED` və digər səbəblər ayrıca saxlanır. Yalnız qəbul edilmiş nümunə Mission Control qrafikinə, AI analizinə və Digital Twin-ə daxil olur. Ssenarilər təhlükəsiz virtual testdir; rədd səbəbi real hücumçu haqqında iddia deyil.

Virtual Device idarəetmə sorğuları yalnız `VIRTUAL` roluna, monitorinq və hesabat API-ləri yalnız monitorinq rollarına açıqdır. `virtual` hesabı məhdud `/api/v1/virtual-device/ws`, `admin` isə `/api/v1/telemetry/ws` WebSocket kanalından istifadə edir. Hər iki kanal sessiyanı yoxlayır və çıxışdan sonra bağlanır.
