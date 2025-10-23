from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
import sqlite3
import os
import uuid
from pdf_service import convert_sheets_to_pdf
import pytz
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'mayatech_screen_manager_secret_key_2024'

# Türkiye saat dilimi
TURKEY_TZ = pytz.timezone('Europe/Istanbul')

def get_turkey_time():
    """Türkiye saatini döndür"""
    now = datetime.now(TURKEY_TZ)
    return now.strftime('%d.%m.%Y %H:%M:%S')

def get_db():
    conn = sqlite3.connect('mayatech.db')
    conn.row_factory = sqlite3.Row
    return conn

# Veritabanı başlatma
def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS screens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            sheets_url TEXT NOT NULL,
            pdf_path TEXT,
            location TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # DETAYLI LOG TABLOSU
    conn.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT NOT NULL,
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Varsayılan kullanıcı - Solpro / solpro
    try:
        conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', ('Solpro', 'solpro'))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    
    conn.close()

# Log fonksiyonu
def log_activity(username, action, details=None):
    """Kullanıcı aktivitesini logla"""
    conn = get_db()
    conn.execute('''
        INSERT INTO activity_logs (username, action, details, ip_address, user_agent)
        VALUES (?, ?, ?, ?, ?)
    ''', (username, action, details, request.remote_addr, request.headers.get('User-Agent')))
    conn.commit()
    conn.close()

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('admin'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ? AND password = ?',
            (username, password)
        ).fetchone()
        conn.close()
        
        if user:
            session['username'] = username
            log_activity(username, 'Giriş yapıldı', f'IP: {request.remote_addr}')
            return redirect(url_for('admin'))
        else:
            flash('Kullanıcı adı veya şifre hatalı')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'username' in session:
        log_activity(session['username'], 'Çıkış yapıldı')
        session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/admin')
def admin():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    screens = conn.execute('SELECT * FROM screens ORDER BY created_at DESC').fetchall()
    
    # Ekran oluşturma saatlerini Türkiye saatine çevir
    formatted_screens = []
    for screen in screens:
        screen_dict = dict(screen)
        if screen_dict['created_at']:
            try:
                # UTC'den Türkiye saatine çevir
                from datetime import datetime
                utc_time = datetime.fromisoformat(screen_dict['created_at'].replace('Z', '+00:00'))
                turkey_time = utc_time.astimezone(TURKEY_TZ)
                screen_dict['created_at'] = turkey_time.strftime('%d.%m.%Y %H:%M:%S')
            except:
                screen_dict['created_at'] = screen_dict['created_at']
        formatted_screens.append(screen_dict)
    
    conn.close()
    
    return render_template('admin.html', screens=formatted_screens, current_time=get_turkey_time())

@app.route('/admin/logs')
def logs():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    logs = conn.execute('SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT 100').fetchall()
    
    # Log saatlerini Türkiye saatine çevir
    formatted_logs = []
    for log in logs:
        log_dict = dict(log)
        if log_dict['created_at']:
            try:
                # UTC'den Türkiye saatine çevir
                from datetime import datetime
                utc_time = datetime.fromisoformat(log_dict['created_at'].replace('Z', '+00:00'))
                turkey_time = utc_time.astimezone(TURKEY_TZ)
                log_dict['created_at'] = turkey_time.strftime('%d.%m.%Y %H:%M:%S')
            except:
                log_dict['created_at'] = log_dict['created_at']
        formatted_logs.append(log_dict)
    
    conn.close()
    
    return render_template('logs.html', logs=formatted_logs, current_time=get_turkey_time())

@app.route('/admin/settings', methods=['GET', 'POST'])
def settings():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        new_username = request.form['username']
        new_password = request.form['password']
        
        conn = get_db()
        conn.execute(
            'UPDATE users SET username = ?, password = ? WHERE username = ?',
            (new_username, new_password, session['username'])
        )
        conn.commit()
        conn.close()
        
        log_activity(session['username'], 'Ayarlar güncellendi', f'Yeni kullanıcı: {new_username}')
        session['username'] = new_username
        flash('Ayarlar başarıyla güncellendi')
        return redirect(url_for('admin'))
    
    return render_template('settings.html', current_time=get_turkey_time())

@app.route('/admin/screens/create', methods=['POST'])
def create_screen():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    name = request.form['name']
    sheets_url = request.form['sheets_url']
    location = request.form.get('location', '')
    
    try:
        # PDF oluştur
        pdf_path = convert_sheets_to_pdf(sheets_url)
        
        # Slug oluştur
        slug = str(uuid.uuid4())[:8]
        
        # Veritabanına kaydet
        conn = get_db()
        conn.execute('''
            INSERT INTO screens (name, slug, sheets_url, pdf_path, location)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, slug, sheets_url, pdf_path, location))
        conn.commit()
        conn.close()
        
        log_activity(session['username'], 'Ekran oluşturuldu', f'Ekran: {name}, Lokasyon: {location}')
        flash('Ekran başarıyla oluşturuldu')
        
    except Exception as e:
        log_activity(session['username'], 'Ekran oluşturma hatası', f'Hata: {str(e)}')
        flash(f'Ekran oluşturulamadı: {str(e)}')
    
    return redirect(url_for('admin'))

@app.route('/admin/screens/<int:screen_id>/edit', methods=['GET', 'POST'])
def edit_screen(screen_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    screen = conn.execute('SELECT * FROM screens WHERE id = ?', (screen_id,)).fetchone()
    
    if request.method == 'POST':
        name = request.form['name']
        sheets_url = request.form['sheets_url']
        location = request.form.get('location', '')
        
        try:
            # Önce eski PDF'i sil
            if screen['pdf_path'] and os.path.exists(screen['pdf_path']):
                os.remove(screen['pdf_path'])
                
            # Yeni PDF oluştur
            pdf_path = convert_sheets_to_pdf(sheets_url)
            
            # Güncelle
            conn.execute('''
                UPDATE screens SET name = ?, sheets_url = ?, pdf_path = ?, location = ?
                WHERE id = ?
            ''', (name, sheets_url, pdf_path, location, screen_id))
            conn.commit()
            
            log_activity(session['username'], 'Ekran düzenlendi', f'Ekran: {name}')
            flash('Ekran başarıyla güncellendi')
            return redirect(url_for('admin'))
            
        except Exception as e:
            log_activity(session['username'], 'Ekran düzenleme hatası', f'Hata: {str(e)}')
            flash(f'Ekran güncellenemedi: {str(e)}')
    
    conn.close()
    return render_template('edit_screen.html', screen=screen, current_time=get_turkey_time())

@app.route('/admin/screens/<int:screen_id>/delete', methods=['POST'])
def delete_screen(screen_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    screen = conn.execute('SELECT * FROM screens WHERE id = ?', (screen_id,)).fetchone()
    
    if screen:
        # PDF dosyasını sil
        if screen['pdf_path'] and os.path.exists(screen['pdf_path']):
            os.remove(screen['pdf_path'])
        
        # Veritabanından sil
        conn.execute('DELETE FROM screens WHERE id = ?', (screen_id,))
        conn.commit()
        
        log_activity(session['username'], 'Ekran silindi', f'Ekran: {screen["name"]}')
        flash('Ekran başarıyla silindi')
    
    conn.close()
    return redirect(url_for('admin'))

@app.route('/screens/<slug>')
def screen_display(slug):
    conn = get_db()
    screen = conn.execute('SELECT * FROM screens WHERE slug = ?', (slug,)).fetchone()
    
    if not screen:
        conn.close()
        return 'Ekran bulunamadı', 404
    
    # PDF YENİLEME MANTIĞI - Her ekran görüntülemede PDF'i güncelle
    try:
        # Önce eski PDF'i sil
        if screen['pdf_path'] and os.path.exists(screen['pdf_path']):
            os.remove(screen['pdf_path'])
            
        # Yeni PDF'i indir ve kaydet
        new_pdf_path = convert_sheets_to_pdf(screen['sheets_url'])
        
        # Veritabanını güncelle
        conn.execute('UPDATE screens SET pdf_path = ? WHERE id = ?', (new_pdf_path, screen['id']))
        conn.commit()
        
        # Güncellenmiş screen bilgisini al
        screen = conn.execute('SELECT * FROM screens WHERE slug = ?', (slug,)).fetchone()
        
    except Exception as e:
        # PDF güncelleme hatası durumunda eski PDF'i kullan
        if not screen['pdf_path'] or not os.path.exists(screen['pdf_path']):
            conn.close()
            return 'PDF dosyası bulunamadı ve güncellenemedi.', 404
    
    conn.close()
    
    # PDF dosyasının varlığını kontrol et
    if not screen['pdf_path'] or not os.path.exists(screen['pdf_path']):
         return 'PDF dosyası sunucuda bulunamadı.', 404

    # Şablonu render et, PDF yolu şablona gönderilecek
    return render_template('screen_display.html', screen=screen, current_time=get_turkey_time())

# PDF dosyalarını sunmak için yeni route
@app.route('/static/pdfs/<filename>')
def serve_pdf(filename):
    response = send_from_directory('static/pdfs', filename)
    
    # Cache bypass headers
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8080, debug=True)
