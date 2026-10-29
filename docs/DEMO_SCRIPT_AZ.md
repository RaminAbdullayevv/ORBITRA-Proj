# ORBITRA təqdimat ardıcıllığı

ORBITRA — Raket Sistemləri üçün Ağıllı Telemetriya və Virtual Sınaq Platforması. Raket sistemlərini fiziki risk olmadan sına, izlə və qoru.

Başlamazdan əvvəl README-dəki backend migrasiyası, `setup_security` və frontend komandalarını yerinə yetirin. [Giriş səhifəsində](http://localhost:5173/login) lokal `admin / admin` hesabı ilə daxil olun. Mövcud SQLite bazasını sıfırlamayın.

| Ardıcıllıq | Səhifə | Göstəriləcək fakt |
| --- | --- | --- |
| 1 | Missiya İdarəetmə | Sınağa hazırlıq əvvəlcə “MƏLUMAT YOXDUR”; yeni ssenari başlananda backend-dən canlı status və qrafiklər gəlir. |
| 2 | Virtual Raket Sistemi | Altı bloklu SVG raket sxemi, sensorlar, Start/Dayandır/Davam etdir/Sıfırla əmrləri və cari sessiya. |
| 3 | Rəqəmsal Model | Yalnız qəbul edilmiş paketlər altı blokun rəngini dəyişir. |
| 4 | AI Analizi və Xəbərdarlıqlar | İlk 20 ardıcıl nümunədən sonra normal baza ilə müqayisə və izahlı AI hadisəsi. |
| 5 | Telemetriya Etibarlılığı | Sentinel yoxlama mərhələləri, sübutlar, yekun qərar və karantin. |
| 6 | Təhlükəsizlik Mərkəzi | Paket rəddi, insident və audit qeydləri. |
| 7 | Missiya Hesabatı | Bir sessiyanın saxlanmış nəticələri və A4 PDF kimi çap. |

## Ssenari axını

1. **Normal raket sistemi sınağı** seçib “Ssenarini başlat” basın. Təxminən bir saniyə sonra qəbul edilmiş ilk nümunəni, sxemin rəngini və qrafiki göstərin. Dayandır/Davam etdir eyni sessiyada işləyir.
2. Sessiyanı bitirib **Bort sistemində temperatur anomaliyası** başladın. Üç temperatur kanalı, cərəyan və virtual yükün birlikdə dəyişməsini, qayda xəbərdarlığını və AI izahını göstərin. “Virtual yükü azalt” əmri sonrakı ölçmələrə təsir edir.
3. Bitirib **Temperatur sensorunda nasazlıq** başladın. Sentinel qərarında sensor 1 uyğunsuzluğunu, Rəqəmsal Modeldə ayrıca sensor xəbərdarlığını göstərin. Digər istilik kanalları bunu təsdiqləmirsə bütün istilik bloku kritik olmur.
4. Bitirib **Etibarsız telemetriya paketi** başladın. #10 paket format rəddinə düşür: Telemetriya Etibarlılığı və Təhlükəsizlik Mərkəzində karantin/audit var, qrafikdə sıra boşluğu görünür və AI onu qəbul edilmiş pəncərəyə daxil etmir.
5. Bitirib **Yanlış imzalı paket** və ya **Təkrar göndərilmiş paket** ssenarisini göstərin. İmza/sıra rəddi ayrıca qeyd olunur.
6. Sessiyanı bitirib Missiya Hesabatını açın və PDF kimi çap edin.

Sınağa hazırlıq virtual sınaq göstəricisidir, real buraxılış qərarı deyil. AI balı nasazlıq ehtimalı deyil. Heç bir real raketə qoşulmayıb.
