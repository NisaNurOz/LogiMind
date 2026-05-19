# 🗺️ LogiMind - Kapasiteli Araç Rotalama (CVRP) ve Lojistik Yönetim Sistemi

LogiMind, lojistik ve dağıtım operasyonlarını optimize etmek amacıyla geliştirilmiş dinamik bir araç rotalama uygulamasıdır. Gelişmiş matematiksel modelleme kütüphanelerini temel alarak Kapasiteli Araç Rotalama Problemini (CVRP) çözer ve araç filolarının en verimli rotaları çizmesini sağlayarak maliyet ve zaman tasarrufu sunar.

## 🚀 Canlı Uygulama Linki
Uygulamayı tarayıcınızda anında deneyimlemek için aşağıdaki bağlantıya tıklayabilirsiniz:
👉 **[LogiMind Canlı Demo](https://logimind-9kbhgzk3cafzhmz3x8cwqf.streamlit.app/)**

---

## ✨ Öne Çıkan Özellikler

* **Dinamik Müşteri ve Konum Yönetimi:** Kullanıcılar arayüz üzerindeki entegre tablo aracılığıyla gerçek zamanlı olarak yeni müşteriler ekleyebilir, X-Y koordinatlarını ve talep miktarlarını anlık olarak güncelleyebilirler.
* **İnteraktif Harita Entegrasyonu:** Seçilen veya güncellenen müşteri ve depo konumları interaktif harita üzerinde anlık görselleştirilir. Haritaya doğrudan tıklayarak nokta ataması yapılabilir.
* **Esnek Senaryo Parametreleri:** Araç sayısı, araç kapasitesi ve trafik/maliyet çarpanları gibi kritik değişkenler yan panelden dinamik olarak değiştirilerek farklı senaryolar anında test edilebilir.
* **Büyük Veri Desteği (CSV):** Gerçek hayat senaryolarına tam uyum sağlaması adına sistem, tek tek veri girmek yerine CSV dosyası üzerinden toplu müşteri listesi yüklenmesini destekler.
* **Yapay Zeka Asistanı:** Arka planda çalışan Gemini AI entegrasyonu ile kullanıcıların lojistik süreçlerine ve rotalama çıktılarına akıllı asistan desteği sunulmaktadır.

---

## 🛠️ Teknoloji Yığını (Tech Stack)

Projenin geliştirilmesinde aşağıdaki güçlü kütüphane ve teknolojilerden yararlanılmıştır:

* **Arayüz & Dağıtım:** [Streamlit](https://streamlit.io/)
* **Optimizasyon Motoru:** [Google OR-Tools](https://developers.google.com/optimization)
* **Haritalama & Görselleştirme:** [Folium / Streamlit-Folium](https://python-visualization.github.io/folium/)
* **Veri Yönetimi:** [Pandas](https://pandas.pydata.org/)
* **Yapar Zeka:** [Gemini AI API](https://ai.google.dev/)
* **Dil:** Python 3.x

---

## 💻 Yerel Bilgisayarda Çalıştırma (Kurulum)

Projeyi kendi bilgisayarınızda çalıştırmak isterseniz:

1. Bu depoyu klonlayın:
   ```bash
   git clone [https://github.com/NisaNurOz/LogiMind.git](https://github.com/NisaNurOz/LogiMind.git)
   cd LogiMind
 
   pip install -r requirements.txt
   streamlit run app.py
