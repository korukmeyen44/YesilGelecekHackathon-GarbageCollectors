"""Export an offline jury report from the current mock DB without changing any records.

python -m app.mock_report
Optional plotting dependency: pip install -r app/requirements-analysis.txt
"""
from __future__ import annotations

import argparse
from datetime import datetime
import html
import hashlib
import io
import json
import re
from pathlib import Path
import sys

from app.mock_audit import analyze, read_snapshot, local_date, ISTANBUL

ROOT = Path(__file__).resolve().parent
GREEN = "#177655"
AMBER = "#bb8426"
BLUE = "#537da4"


def nf(value, digits=1):
    return f"{value:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def build_figures(data, audit, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np
    plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":10, "axes.spines.top":False,
                         "axes.spines.right":False, "axes.edgecolor":"#ccd6d1", "text.color":"#243a31",
                         "axes.labelcolor":"#4e6658", "xtick.color":"#708477", "ytick.color":"#708477",
                         "figure.facecolor":"white", "savefig.facecolor":"white"})
    bins = sorted(audit["bins"], key=lambda b:(b["base_rate_pph"],b["id"]))
    now = audit["demo_now"]
    slow = min(bins, key=lambda b:b["base_rate_pph"])["id"]
    fast = max(bins, key=lambda b:(b["base_rate_pph"], -int(b["id"][1:])))["id"]
    middle = min(bins, key=lambda b:(abs(b["base_rate_pph"]-2),b["id"]))["id"]
    examples = [(fast, "Çok hızlı", AMBER), (middle, "Orta", GREEN), (slow, "Çok yavaş", BLUE)]

    def rate_plot(ax, compact=False):
        y=np.arange(len(bins)); rates=[b["base_rate_pph"] for b in bins]
        ax.barh(y,rates,color=[AMBER if r>=6 else BLUE if r<1 else GREEN for r in rates],height=.7)
        ax.set_yticks(y,[b["id"] for b in bins],fontsize=8 if compact else 10)
        ax.set_xlim(0,max(rates)*1.2)
        ax.set_xlabel("Tanımlı temel hız (yüzde puan / saat)")
        ax.grid(axis="x",alpha=.15);ax.set_axisbelow(True)
        for row,rate in zip(y,rates):ax.text(rate+.1,row,nf(rate),va="center",fontsize=8 if compact else 10)
        counts=set(audit["base_rates"].values())
        count_text=f"her profilden {next(iter(counts))} kutu" if len(counts)==1 else "farklı sayıda kutu"
        ax.set_title(f"{len(audit['base_rates'])} hız profili; {count_text}",loc="left",fontweight="bold",pad=14)

    def time_axis(ax):
        ax.set_ylim(-3,105);ax.set_ylabel("Doluluk (%)")
        ax.axhline(80,color=AMBER,lw=1,ls="--",alpha=.7)
        ax.set_xlim(local_date(now-72*3600),local_date(now))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4,maxticks=7))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m\n%H:%M",tz=ISTANBUL))
        ax.grid(alpha=.12)

    def history_plot(ax, ident, label, color, annotate=True):
        rows=[r for r in data["samples"][ident] if now-72*3600<=r[0]<=now]
        # Invalid quality / gaps must not turn into a visually continuous valid series.
        xs,ys=[],[];previous=None
        for stamp,fill,quality in rows:
            if previous is not None and stamp-previous>1350:
                xs.append(local_date(stamp));ys.append(float("nan"))
            xs.append(local_date(stamp));ys.append(fill if quality in ("ok","degraded") and fill is not None else float("nan"))
            previous=stamp
        ax.plot(xs,ys,color=color,lw=1.5,label=ident+" · "+label)
        if annotate:
            stat=next(b for b in bins if b["id"]==ident)
            drops=[t for t,_ in stat["drops"] if now-72*3600<=t<=now]
            ax.scatter([local_date(t) for t in drops],[4]*len(drops),marker="v",color=color,s=20,zorder=4)
            ax.set_title(f"{ident} · {label} · {nf(stat['base_rate_pph'])} yüzde puan/saat",loc="left",fontweight="bold",pad=10)
        time_axis(ax)

    days=sorted({day for b in bins for day in b["daily_rate_pph"]})
    values=np.array([[b["daily_rate_pph"].get(day,float("nan")) for day in days] for b in bins])
    def daily_plot(ax, compact=False):
        cmap=plt.get_cmap("YlGnBu").copy();cmap.set_bad("#e9edf0")
        image=ax.imshow(np.ma.masked_invalid(values),aspect="auto",cmap=cmap,vmin=0,vmax=max(8,float(np.nanmax(values))))
        ax.set_yticks(range(len(bins)),[b["id"] for b in bins],fontsize=8 if compact else 10)
        stride=2 if compact else 1
        ticks=list(range(0,len(days),stride))
        ax.set_xticks(ticks,[datetime.fromisoformat(days[i]).strftime("%d.%m") for i in ticks],rotation=45,ha="right",fontsize=8 if compact else 10)
        ax.set_xlabel("Yerel tarih (UTC+03); ilk ve son gün kısmi olabilir")
        ax.set_title("Kutu × gün: gözlenen ortanca artış hızı",loc="left",fontweight="bold",pad=14)
        colorbar=ax.figure.colorbar(image,ax=ax,fraction=.025,pad=.025)
        colorbar.set_label("Yüzde puan / saat",fontsize=9)

    def spatial_plot(ax, compact=False):
        points=ax.scatter([b["lng"] for b in bins],[b["lat"] for b in bins],
                          c=[b["base_rate_pph"] for b in bins],cmap="YlGnBu",vmin=0,vmax=8,s=65 if compact else 100,
                          edgecolors="#385a47",linewidths=.5)
        for b in bins:ax.annotate(b["id"],(b["lng"],b["lat"]),xytext=(5,4),textcoords="offset points",fontsize=7 if compact else 9)
        ax.set_xlabel("Boylam");ax.set_ylabel("Enlem")
        ax.ticklabel_format(useOffset=False)
        ax.tick_params(axis="x",labelrotation=20,labelsize=8 if compact else 10)
        ax.grid(alpha=.15);ax.margins(.15)
        ax.set_title("Koordinat grafiği: hızlar nerede?",loc="left",fontweight="bold",pad=14)
        cb=ax.figure.colorbar(points,ax=ax,fraction=.035,pad=.025);cb.set_label("Tanımlı hız (yp/saat)",fontsize=9)

    svg_count = 0
    def svg(fig):
        nonlocal svg_count
        svg_count += 1
        stream=io.StringIO();fig.savefig(stream,format="svg",bbox_inches="tight")
        text=stream.getvalue();plt.close(fig)
        text=text[text.index("<svg"):]
        prefix=f"audit-{svg_count}-"
        text=re.sub(r'id="([^"]+)"',lambda m:'id="'+prefix+m[1]+'"',text)
        return text.replace('href="#','href="#'+prefix).replace('url(#','url(#'+prefix)

    figures={}
    fig,ax=plt.subplots(figsize=(11.4,6.8),layout="constrained");rate_plot(ax);figures["rates"]=svg(fig)
    fig,axes=plt.subplots(3,1,figsize=(11.4,8.2),sharex=True,layout="constrained")
    for ax,(ident,label,color) in zip(axes,examples):history_plot(ax,ident,label,color)
    figures["history"]=svg(fig)
    fig,ax=plt.subplots(figsize=(11.4,6.8),layout="constrained");daily_plot(ax);figures["daily"]=svg(fig)
    fig,ax=plt.subplots(figsize=(11.4,6.8),layout="constrained");spatial_plot(ax);figures["spatial"]=svg(fig)
    fig,axes=plt.subplots(2,2,figsize=(17,10.5),layout="constrained")
    rate_plot(axes[0,0],True)
    for ident,label,color in examples:history_plot(axes[0,1],ident,label,color,False)
    axes[0,1].legend(fontsize=9,loc="upper left",ncol=3)
    axes[0,1].set_title("Son 72 saat: hızlı, orta ve yavaş dolum",loc="left",fontweight="bold",pad=14)
    daily_plot(axes[1,0],True);spatial_plot(axes[1,1],True)
    fig.suptitle(f"MOCK VERİ İNCELEMESİ  |  {audit['bins_count']} kutu · {nf(audit['span_days'],0)} gün · {nf(audit['samples_count'],0)} kayıt",fontsize=18,fontweight="bold")
    fig.supxlabel("Tamamı sentetik veridir. Koordinat grafiği coğrafi heatmap değildir; hız üretici parametresidir, model tahmini değildir.",fontsize=10)
    fig.savefig(output/"mock-veri-ozeti.png",dpi=150);plt.close(fig)
    return figures


def report_text(a, figures):
    e=html.escape
    cases=[("S03","Orta dolulukta hızlı dolum"),("S13","Yavaş dolum / azami toplama aralığı"),
           ("S19","Düşük seviyede hızlı dolum"),("S22","Bağlantı kesintisi"),("S23","Geçersiz ölçüm"),("S24","Kısmi ölçüm kalitesi")]
    case_rows="".join(f"<tr><td><b>{ident}</b><br>{e(label)}</td><td>{'Belirsiz' if a['decisions'][ident]['fill'] is None else '%'+nf(a['decisions'][ident]['fill'])}</td><td>{e(' '.join(a['decisions'][ident]['reasons']))}</td></tr>" for ident,label in cases if ident in a["decisions"])
    source_time=local_date(a["demo_now"]).strftime("%d.%m.%Y %H:%M")
    mean_neighbors=a["neighbor_rate_correlation"]
    corr_note="Hesaplanamadı" if mean_neighbors is None else nf(mean_neighbors,2)
    quality_ok=a["quality_counts"].get("ok",0)
    coverage_rows=[
        ("Farklı dolum hızları","VAR",f"{len(a['base_rates'])} hız profili; {nf(a['rate_min'])}–{nf(a['rate_max'])} yüzde puan/saat. En hızlı / en yavaş oranı {nf(a['rate_ratio'])}."),
        ("Doluluk ve erken uyarı demosu","VAR","Dolu, orta dolu ama hızlı artan, düşük dolu ve ertelenebilir örnekler mevcut. Karar örnekleri aşağıda."),
        ("Geçmiş uzunluğu","SINIRLI",f"{nf(a['span_days'],0)} gün; iki haftalık döngü. Basit eğilim demosuna uygun; haftalık model genellemesine ilişkin kanıt sınırlı."),
        ("Gündüz/gece farkı","KISMEN","Üreticide ortak gece/gündüz katsayısı var. Son dolum dönemi hedef son seviyeye doğrusal bağlandığı için bu örüntü bazı kutularda kayboluyor."),
        ("Hafta sonu / etkinlik / tatil","YOK","Bu üretici sürümünde bu durumlara özgü takvim veya bölgesel davranış parametresi yok."),
        ("Geçmişte arıza ve eksik veri", "YOK" if quality_ok==a['samples_count'] and not a['missing_slots_estimate'] else "KONTROL",f"{nf(quality_ok,0)} kayıt ok; tahmini eksik zaman yuvası {a['missing_slots_estimate']}. Mevcut offline/unstable/degraded bayrakları geçmişe yayılmış arıza senaryosu değildir."),
        ("Boşaltma olayları","DÜZELTİLMELİ",f"{a['collection_records']} olay kaydı, {a['observed_drops']} gözlenen >20 puan düşüş. {a['same_drop_extra_records']} ilave olay aynı düşüş aralığına denk geliyor; {a['unconfirmed_collection_records']} olayda bu büyüklükte düşüş doğrulanmıyor."),
        ("Coğrafi yoğunluk verisi","KISMEN",f"Konumlar var; bölgeye bağlı dolum süreci açıkça modellenmemiş. Tanımlı hız ile 3 en yakın komşunun ortalama hızının korelasyonu {corr_note}; bu bir anlamlılık testi değildir."),
        ("Kapasite çeşitliliği","YOK" if len(a['capacities_l'])==1 else "VAR",f"Nominal kapasite değerleri: {', '.join(nf(v,0) for v in a['capacities_l'])} L. Ağırlık veya gerçek atık hacmi ölçülmüyor."),
        ("Gerçek veride tahmin başarısı","ÖLÇÜLMEDİ","Sentetik veride model davranışı incelenebilir; gerçek sensör/saha başarısı bu veriden çıkarılamaz."),
    ]
    coverage="".join(f"<tr><td>{e(label)}</td><td><span class='tag'>{e(status)}</span></td><td>{e(text)}</td></tr>" for label,status,text in coverage_rows)
    all_bins="".join(f"<tr><td>{b['id']}</td><td>{e(b['area'])}</td><td>{nf(b['base_rate_pph'])}</td><td>{'—' if b['observed_median_pph'] is None else nf(b['observed_median_pph'],2)}</td><td>{b['samples']}</td><td>{b['collection_records']} / {b['observed_drops']}</td><td>{e(b['current_fault'])}</td></tr>" for b in a["bins"])
    sections=[
        ("hizlar","Hız çeşitliliği",figures["rates"],"Bunlar üreticiye tanımlanan temel hızlardır; öğrenilmiş veya gerçek sahada ölçülmüş hızlar değildir. Birden fazla kutu aynı temel hızı paylaşır; kutu sayısı bağımsız davranış ailesi sayısı değildir."),
        ("zaman","Aynı zaman aralığında üç davranış",figures["history"],"Son 72 saat aynı doluluk ölçeğinde karşılaştırılıyor. Kesikli çizgi %80 toplama eşiği; aşağı bakan işaretler gözlenen büyük düşüşlerdir. Bağlantı boşlukları çizgiyle birleştirilmez."),
        ("matris","Zaman × kutu ısı matrisi",figures["daily"],"Her hücre, boşaltma/arıza/boşluk içermeyen bir saatlik pencerelerin günlük ortanca net artışıdır. Kısmi günler ve pencere sayıları farklı olabilir. Bu, coğrafi yoğunluk heatmap'i değildir. Veri yoksa hücre gri kalır."),
        ("konum","Mekânsal çeşitlilik kontrolü",figures["spatial"],"Konumlar kampüs çevresine yaklaşık yerleştirilmiş demo noktalarıdır. Bu bir koordinat dağılım grafiğidir; coğrafi zemin veya KDE içermez. Kutu sayısı yoğunluğu, anlık doluluk ve dolum hızı farklı büyüklüklerdir."),
    ]
    charts="".join(f"<section id='{key}'><h2>{title}</h2><figure aria-label='{e(title)}'>{svg}<figcaption>{e(caption)}</figcaption></figure></section>" for key,title,svg,caption in sections)
    limitations="".join(f"<li>{e(s)}</li>" for s in a["limitations"])
    body=f"""<header><div class='eyebrow'>GARBAGE COLLECTORS · VERİ DENETİMİ</div><h1>Mock veri kapsamı ve davranışları</h1><p class='lead'>Mevcut veri temel operasyon demosunu destekliyor. İleri zaman serisi değerlendirmesi ve bölgesel yoğunluk senaryoları için veri üreticisi güçlendirilmeli.</p><p><b>Tamamı sentetik veridir.</b> Gerçek belediye kaydı veya gerçek sensör başarısı olarak sunulmaz.</p><div class='meta'>Veri anı: {source_time} (UTC+03) · {a['bins_count']} kutu · {nf(a['span_days'],0)} gün · {nf(a['samples_count'],0)} kayıt<br>Kaynak: {e(a.get('source_database','SQLite simülasyon deposu'))} anlık görüntüsü · veri özeti SHA-256: <code>{a['source_digest']}</code></div></header>
    <nav aria-label='Rapor bölümleri'><a href='#kapsam'>Kapsam</a><a href='#hizlar'>Hızlar</a><a href='#zaman'>Zaman serileri</a><a href='#matris'>Isı matrisi</a><a href='#konum'>Konumlar</a><a href='#ornekler'>Demo örnekleri</a><a href='#gelisim'>Geliştirme ihtiyacı</a></nav>
    <section id='kapsam'><h2>Hangi örnekler gerçekten var?</h2><div class='table-wrap'><table><thead><tr><th>İhtiyaç</th><th>Durum</th><th>Bulgu</th></tr></thead><tbody>{coverage}</tbody></table></div></section>{charts}
    <section id='ornekler'><h2>Jüri önünde gösterilebilecek mevcut örnekler</h2><p>Bu kararlar dondurulmuş demo zamanındaki varsayılan/kalıcı operasyon ayarlarıyla tekrar hesaplandı. Sonradan veri veya eşik değişirse sonuç da değişir.</p><div class='table-wrap'><table><thead><tr><th>Örnek</th><th>Doluluk</th><th>Mevcut kuralın gerekçesi</th></tr></thead><tbody>{case_rows}</tbody></table></div></section>
    <section id='gelisim'><h2>Sonraki veri üreticisi için önerilen kapsam</h2><p><b>Aşağıdakiler öneridir; mevcut veri setinde uygulanmış değildir.</b></p><ol><li>8–12 haftalık, tekrarlanabilir seed ve sürüm numarası taşıyan geçmiş; son haftaları zaman sırasıyla test için ayırma. Bu süre bir tasarım önerisidir, bilimsel yeterlilik garantisi değildir.</li><li>Bölgeye bağlı hızlı/orta/yavaş kümeler; gündüz, gece ve hafta sonuna göre farklı profiller. Etkinlik/ani yük ve davranış değişimi senaryolarını ayrı etiketleme.</li><li>Temel dolum süreci, gözlenen sensör verisi ve toplama olaylarını ayrı tutma; boşaltmayı tek olayla kaydetme.</li><li>Geçmişte kesinti, kararsız ölçüm, kısmi kalite ve kalibrasyon değişikliği; eksik değeri sıfıra dönüştürmeme.</li><li>Heatmap için büyüklüğü seçme: anlık doluluk yükü mü, zaman başına birikim mi? Nokta sayısı ve kapasite etkisini ayrıca görünür tutma.</li><li>Modelde yalnız tahmin anında bilinebilen özellikleri kullanma. Üreticiye ait rate/gerçek gelecek dolum parametrelerini modele vermeme; basit son-değer ve eğilim tahminiyle karşılaştırma.</li></ol><h3>İnceleme sınırları</h3><ul>{limitations}</ul></section>
    <section><h2>{a['bins_count']} kutunun özeti</h2><details><summary>Tüm kutuların sayısal dökümünü aç</summary><div class='table-wrap'><table><thead><tr><th>Kutu</th><th>Bölge</th><th>Tanımlı hız (yp/saat)</th><th>Gözlenen ortanca (yp/saat)</th><th>Kayıt</th><th>Toplama kaydı / büyük düşüş</th><th>Şimdiki durum</th></tr></thead><tbody>{all_bins}</tbody></table></div></details></section>
    <footer><p>Rapor, mevcut depo salt okunur açılarak üretildi. Veri, kalibrasyon, donanım ve çalışan demo durumu değiştirilmedi. Grafikler HTML içine gömülüdür; görüntülemek için internet veya çalışan backend gerekmez.</p><p>Üreticiye ilişkin kapsam yorumları incelenen storage.py sürümüne aittir; üretici değiştirilirse değerlendirme de yenilenmelidir. Üretici SHA-256: <code>{a.get('generator_source_sha256','—')}</code></p><p>Yöntem kaynakları: <a href='https://otexts.com/fpp3/toolbox.html#time-series-cross-validation'>Hyndman ve Athanasopoulos — zaman serisi doğrulaması</a> · <a href='https://docs.qgis.org/3.40/en/docs/user_manual/processing_algs/qgis/interpolation.html#heatmap-kernel-density-estimation'>QGIS — KDE, ağırlık ve yarıçap</a></p></footer>"""
    css="""*{box-sizing:border-box}body{margin:0;background:#f4f7f4;color:#243a31;font:15px/1.75 'Segoe UI',Arial,sans-serif}main{max-width:1150px;margin:35px auto;background:white;padding:42px 52px;border:1px solid #dfe7e0;border-radius:12px}h1{font-size:34px;letter-spacing:-1px;line-height:1.2;margin:10px 0 20px}h2{font-size:23px;line-height:1.3;margin:0 0 18px}h3{font-size:17px}.eyebrow{color:#177655;letter-spacing:1.5px;font-weight:700;font-size:11px}.lead{font-size:19px;line-height:1.6;max-width:900px}.meta{font-size:12px;color:#6b7e70;border-top:1px solid #e4ebe4;padding-top:15px}code{font-size:11px;overflow-wrap:anywhere}section{padding:35px 0;border-top:1px solid #e4ebe4;scroll-margin-top:15px}nav{display:flex;flex-wrap:wrap;gap:8px 20px;margin:27px 0}a{color:#177655;text-underline-offset:4px}nav a{font-size:13px}figure{margin:0}figure svg{display:block;width:100%;height:auto}figcaption{font-size:13px;color:#6f8174;line-height:1.7;border-left:3px solid #c7dece;padding-left:14px;margin:18px 0 0}table{width:100%;border-collapse:collapse;text-align:left;font-size:13px}th{background:#edf5ef;color:#50725c;font-size:12px;padding:12px 14px}td{border-bottom:1px solid #e5ece5;padding:13px 14px;vertical-align:top}th:first-child,td:first-child{min-width:150px}.tag{font-weight:700;font-size:10px;white-space:nowrap;color:#7c642d}td:nth-child(2){min-width:100px}.table-wrap{overflow:auto}summary{color:#177655;cursor:pointer;padding:12px 0;font-weight:600}li{margin:10px 0}footer{color:#7b8b7d;font-size:12px;border-top:1px solid #e4ebe4;padding-top:20px}@media(max-width:700px){main{padding:24px 18px;margin:0;border:0;border-radius:0}h1{font-size:28px}.lead{font-size:17px}h2{font-size:21px}table{font-size:12px}td,th{padding:10px}section{padding:25px 0}}@media print{body{background:white}main{border:0;margin:0;padding:0;max-width:none}nav{display:none}figure{break-inside:avoid}h2,h3{break-after:avoid}section{padding:22px 0}details{display:none}a{color:inherit}footer{font-size:9px}@page{size:A4;margin:16mm}}"""
    return "<!doctype html><html lang='tr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Mock veri kapsamı ve davranışları</title><style>"+css+"</style></head><body><main>"+body+"</main></body></html>"


def write_markdown(a, output):
    corr="hesaplanamadı" if a["neighbor_rate_correlation"] is None else f"{a['neighbor_rate_correlation']:.3f}"
    table="\n".join(f"| {b['id']} | {b['base_rate_pph']} | {b['observed_median_pph']} | {b['current_fault']} |" for b in a["bins"])
    text=f"""# Mock veri inceleme sonucu

Mevcut veri temel operasyon demosu için yeterli örnekler içerir. İleri zaman serisi değerlendirmesi ve anlamlı bölgesel yoğunluk senaryoları için kapsam kısmen yeterlidir; üretici güçlendirilmelidir. Bu çalışma veri üreticisini veya veritabanını değiştirmedi.

- {a['bins_count']} simülasyon kutusu, {a['span_days']:g} günlük geçmiş, {a['samples_count']} kayıt.
- {len(a['base_rates'])} temel hız (yüzde puan/saat: kutu sayısı): {', '.join(str(rate)+': '+str(count) for rate,count in a['base_rates'].items())}.
- En hızlı / en yavaş oranı: {a['rate_ratio']:.2f}.
- Kalite alanı: {json.dumps(a['quality_counts'],ensure_ascii=False)}. Tahmini eksik örnek yuvası: {a['missing_slots_estimate']}.
- Mevcut durumlar: {json.dumps(a['current_faults'],ensure_ascii=False)}. Bu bayraklar geçmişteki kesintilerin kanıtı değildir.
- {a['collection_records']} toplama kaydı, {a['observed_drops']} gözlenen büyük düşüş; {a['same_drop_extra_records']} ilave kayıt aynı düşüş aralığıyla eşleşiyor, {a['unconfirmed_collection_records']} kayıtta >20 puan düşüş doğrulanmıyor.
- Veri özeti SHA-256: `{a['source_digest']}`.

## Senaryo yeterliliği

Harita, doluluk eşiği, orta seviyede hızlı dolum, yavaş dolum, elle arıza demosu ve rota adayları için örnekler var. Güncel seviye ile günlük birikim farklı büyüklüklerdir. Toplama, seviyesi düşen bir bölgenin atık üretiminin azaldığı anlamına gelmez.

Zaman serisi için ortak gündüz/gece katsayısı ve küçük rastgele değişim var. Hafta sonu/etkinlik/tatil profili yok. Son dolum dönemi hedef son seviyeye doğrusal bağlanıyor; bazı kutularda birkaç günlük geçmiş bu nedenle düzleşiyor. Üretici hızı modele girdi yapılırsa sonuç yapay biçimde kolaylaşır. 14 gün yalnız iki haftalık tekrar içerir; gerçek genelleme kanıtı değildir.

Koordinatlar heatmap için teknik girdi sağlar. Bölgesel sıcak/soğuk alan üretmek üzere açık bir mekânsal süreç yok. 3 komşunun ortalama hızıyla temel hız korelasyonu {corr}; bu yalnız betimleyici bir kontroldür, anlamlılık testi değildir. Gelecekte heatmap'te nokta sayısı, doluluk yükü ve birikim hızı ayrı tanımlanmalı; KDE ağırlığı ve yarıçapı belirtilmelidir.

## Jüri için seçilen yöntem

`mock-veri-inceleme.html` tek dosyalı, internet gerektirmeyen grafik raporudur. Tanımlı hız çubukları, aynı 72 saatte hızlı/orta/yavaş kutular, kutu × gün ısı matrisi, koordinat dağılım grafiği, karar örnekleri ve sınırlamalar birlikte gösterilir. `mock-veri-ozeti.png` sunuma eklenebilecek görseldir; `mock-veri-inceleme.json` hesaplanan sayısal dökümdür. Rapor kaynak verinin o andaki kopyasına bağlıdır; demo ilerledikçe yeniden üretilmelidir.

## Sonraki veri üreticisi önerisi

8–12 haftalık sürümlü/seed'li geçmiş; bölge ve zaman bağımlı profiller; hafta sonu ve ani yük; gerçek dolum sürecinden ayrı sensör gürültüsü/arıza kayıtları; tekil toplama olayları; eğitim-test ayrımı ve basit tahminlerle karşılaştırma önerilir. Bu bir geliştirme önerisidir, uygulanmış özellik değildir. Sentetik başarıdan gerçek saha başarısı çıkarılamaz.

## Kutular

| Kutu | Tanımlı hız (yp/saat) | Gözlenen ortanca (yp/saat) | Şimdiki durum |
| --- | --- | --- | --- |
{table}

Yöntem kaynakları: [Zaman serisi doğrulaması](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation), [QGIS KDE ağırlık ve yarıçap tanımı](https://docs.qgis.org/3.40/en/docs/user_manual/processing_algs/qgis/interpolation.html#heatmap-kernel-density-estimation).
"""
    (output/"MOCK_VERI_INCELEMESI.md").write_text(text,encoding="utf-8")


def main():
    if hasattr(sys.stdout,"reconfigure"):sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database",type=Path,default=ROOT/".data/operations.sqlite3")
    parser.add_argument("--output-dir",type=Path,default=ROOT/"reports")
    args=parser.parse_args()
    if not args.database.is_file():parser.error("Mevcut demo veritabanı bulunamadı. Araç yeni veri üretmez.")
    data=read_snapshot(args.database);audit=analyze(data)
    audit["source_database"]=args.database.name
    audit["generator_source_sha256"]=hashlib.sha256((ROOT/"storage.py").read_bytes()).hexdigest()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    try:figures=build_figures(data,audit,args.output_dir)
    except ImportError:parser.error("Grafik için python -m pip install -r app/requirements-analysis.txt çalıştırın.")
    # Matplotlib SVG paths may end with spaces; keep generated HTML review-friendly.
    report_html = "\n".join(line.rstrip() for line in report_text(audit,figures).splitlines()) + "\n"
    (args.output_dir/"mock-veri-inceleme.html").write_text(report_html,encoding="utf-8")
    (args.output_dir/"mock-veri-inceleme.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    write_markdown(audit,args.output_dir)
    if read_snapshot(args.database)["digest"] != data["digest"]:
        print("Not: kaynak rapor üretilirken başka işlemle değişti; rapor ilk anlık görüntüyü temsil eder.")
    else:print("PASS: kaynak mock verisi değişmedi (salt okunur inceleme).")
    print(f"Rapor: {(args.output_dir/'mock-veri-inceleme.html').resolve()}")


if __name__=="__main__":main()
