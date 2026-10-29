# ORBITRA virtual kibertəhlükəsizlik demosu

Bu demo yalnız ORBITRA-nın özündə yaradılan virtual telemetriya paketlərini sınaqdan keçirir. Real raketə, təşkilata və ya xarici ünvana paket göndərilmir. Cihaz ekranında sərbəst paket, hədəf və ya zərərli məzmun daxil etmək imkanı yoxdur.

## Üç test

Virtual Device-də **Kiberhücum simulyasiyası** seçin, sonra test növünü seçib ssenarini başladın. Hər başlatma ayrıca run ID yaradır; test paketi həmin run-un 10-cu saniyəsində təqdim edilir.

| Test | Virtual paketdə edilən dəyişiklik | Backend-in müşahidə etməli olduğu səbəb | Təsirlənən məlumat |
| --- | --- | --- | --- |
| Replay | 9-cu saniyənin eyni imzalı paketi təkrar təqdim olunur | `REPLAY_REJECTED` — əvvəl qəbul edilmiş sıra nömrəsi | Telemetriya və rabitə |
| Telemetry Spoofing | Paket qeydiyyatsız virtual mənbə adı ilə təqdim olunur | `SOURCE_REJECTED` — mənbə tanınmır | Telemetriya və rabitə |
| Integrity | Paket imzalandıqdan sonra temperatur 1 dəyəri dəyişdirilir | `INTEGRITY_REJECTED` — HMAC uyğun gəlmir | İstilik bloku, gələn məlumat |

Test paketinin yaranması üçün ssenarini ən azı 10 saniyə işlək saxlayın. Testin adı niyyəti göstərir. Sentinel-in qərarı format, mənbə, imza, sıra və vaxt yoxlamasında **faktiki müşahidə edilən** nəticədən gəlir. Hər rədd paketi və yoxlama sübutu SQLite-də run ID ilə saxlanır; normal qrafikə və AI temperatur pəncərəsinə daxil edilmir. Security Operations hadisəsində “Nə göndərildi → hansı yoxlama uğursuz oldu → sistem nə etdi?” detalı açılır. Digital Twin fiziki vəziyyəti yalnız son qəbul edilmiş nümunədən hesablayır və rədd edilmiş paketin aid olduğu blokda ayrıca məlumat etibarlılığı işarəsi göstərir.

Mission Report hər seçilmiş run üzrə nəticəsi saxlanmış virtual test paketlərini sayır. Düzgün aşkarlandı sayı = paket rədd edilib **və** müşahidə olunan səbəb həmin testin gözlənilən yoxlama səbəbidir. Faiz `düzgün aşkarlandı / nəticəsi saxlanmış test paketləri × 100` qaydası ilə hesablanır. Sınaq yoxdursa faiz göstərilmir. Bu rəqəm real kiberhücumlara qarşı uğur göstəricisi deyil. Üç testi ayrı başladanda hər biri ayrıca run hesabatında görünür; tarixçələr qarışdırılmır.

Saxta mənbə testində [MITRE ATT&CK ICS T1692.002 — Reporting Message](https://attack.mitre.org/techniques/T1692/002/) yalnız nəzəri oxşarlıq kimi qeyd olunur. Replay və dəyişdirilmiş paketə dəqiq texnika təyin edilmir. Etibarsız imza trafikin araya girilərək dəyişdirildiyini və ya hücumçunun kimliyini sübut etmir.

## Lokal təqdimat

[START_HERE.md](../START_HERE.md) ilə bir backend və bir frontend başladın. `http://localhost:5173/login` səhifəsini adi brauzer pəncərəsində `admin` hesabı, gizli pəncərədə `virtual` hesabı ilə açın. Eyni brauzer profilində iki hesabın cookie sessiyası bir-birini əvəz edir. Yeni kodun yüklənməsi üçün əvvəlki açıq başlatma pəncərəsini bağlayıb yenisini başladın.

İctimai domenə yerləşdirmədən əvvəl hər iki lokal demo şifrəsini `backend` qovluğunda `python -m scripts.manage_users change admin` və `python -m scripts.manage_users change virtual` ilə dəyişin. Şifrələr bazada hash kimi saxlanır. Əlavə domen addımları [DEPLOY.md](DEPLOY.md) sənədindədir.

## Məhdudiyyətlər

Bu, məhdud sayda əvvəlcədən müəyyən edilmiş virtual paket sınağıdır; real sənaye sistemi və ya real hücum aktoru modelləşdirilmir. Müşahidə olunan rədd səbəbi qəsd və ya fiziki nasazlıq barədə nəticə vermir. Simulatorun aktiv vəziyyəti backend yenidən başlayanda davam etmir; saxlanmış run, hadisə və hesabatlar bazada qalır.
