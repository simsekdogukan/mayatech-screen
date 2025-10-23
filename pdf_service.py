import requests
import os
import uuid
import glob
from urllib.parse import urlparse, parse_qs

def convert_sheets_to_pdf(sheets_url):
    """
    Google Sheets URL'ini PDF'e dönüştür
    """
    try:
        # URL'yi PDF export formatına çevir
        pdf_url = _convert_to_pdf_url(sheets_url)
        
        # Cache busting için timestamp ekle
        import time
        timestamp = int(time.time())
        if '?' in pdf_url:
            pdf_url += f"&t={timestamp}"
        else:
            pdf_url += f"?t={timestamp}"
        
        # PDF'i indir
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
        
        # Content-Type kontrolü
        content_type = response.headers.get('content-type', '')
        if 'text/html' in content_type:
            raise Exception('PDF indirme hatası: Giriş sayfası döndü')
        
        # Dosya boyutu kontrolü
        if len(response.content) < 1000:
            raise Exception('PDF indirme hatası: Dosya çok küçük')
        
        # PDF dosyasını kaydet - Her seferinde yeni dosya adı
        os.makedirs('static/pdfs', exist_ok=True)
        timestamp = int(time.time())
        filename = f'ekran_{timestamp}_{uuid.uuid4().hex[:8]}.pdf'
        filepath = os.path.join('static/pdfs', filename)
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        # Eski PDF dosyalarını temizle (aynı ekran için)
        _cleanup_old_pdfs()
        
        return filepath
        
    except Exception as e:
        raise Exception(f'PDF oluşturulamadı: {str(e)}')

def _convert_to_pdf_url(sheets_url):
    """
    Google Sheets URL'ini PDF export URL'ine çevir
    """
    # URL'yi parse et
    parsed = urlparse(sheets_url)
    
    # Document ID'yi çıkar
    if '/d/' in sheets_url:
        doc_id = sheets_url.split('/d/')[1].split('/')[0]
    else:
        raise Exception('Geçersiz Google Sheets URL')
    
    # PDF export URL'i oluştur
    pdf_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=pdf&portrait=true&size=A4&fzr=true&fzc=true&attachment=false"
    
    return pdf_url

def _cleanup_old_pdfs():
    """
    Eski PDF dosyalarını temizle (5'ten fazla dosya varsa)
    """
    try:
        pdf_files = glob.glob('static/pdfs/ekran_*.pdf')
        if len(pdf_files) > 5:
            # Dosyaları tarihe göre sırala (en eski önce)
            pdf_files.sort(key=os.path.getmtime)
            
            # En eski dosyaları sil (5'ten fazla varsa)
            for old_file in pdf_files[:-5]:
                try:
                    os.remove(old_file)
                except:
                    pass
    except:
        pass
