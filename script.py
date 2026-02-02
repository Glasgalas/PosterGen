import requests
import datetime
import time
import schedule
import os
import base64
from PIL import Image, ImageDraw, ImageOps, ImageFont, ImageFilter
from io import BytesIO

# --- НАЛАШТУВАННЯ TMDB ---
TMDB_TOKEN = "xxxx" #your TMDB_TOKEN 
TMDB_BASE_URL = "https://api.themoviedb.org/3"
IMG_BASE_URL = "https://image.tmdb.org/t/p/w500"

# --- НАЛАШТУВАННЯ JELLYFIN ---
JF_HOST = "yyyy" #your Server Jellifyn
JF_BASE_URL = "zzzz" #your Jellyfin url
JF_API_KEY = "qqqqq" #your API key Jellyfin

MOVIES_ITEM_ID = "11111" #in browser folder Movies - ParentId=
TV_ITEM_ID = "22222" #in browser folder TV Shows - ParentId=

TARGET_W, TARGET_H = 500, 750 

def get_font(size):
    paths = ["arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:\\Windows\\Fonts\\arial.ttf"]
    for p in paths:
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def get_tmdb_data(media_type):
    today = datetime.date.today()
    last_month = (today - datetime.timedelta(days=30)).isoformat()
    endpoint = "movie" if media_type == "movies" else "tv"
    date_key = "primary_release_date" if media_type == "movies" else "first_air_date"
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}", "accept": "application/json"}
    url = (f"{TMDB_BASE_URL}/discover/{endpoint}?language=uk-UA&region=UA&"
           f"sort_by=vote_average.desc&vote_count.gte=30&"
           f"{date_key}.gte={last_month}&{date_key}.lte={today.isoformat()}&page=1")
    try:
        r = requests.get(url, headers=headers, timeout=20)
        return [item['poster_path'] for item in r.json().get('results', [])[:10] if item['poster_path']]
    except: return []

def draw_neon_label(image, text):
    draw = ImageDraw.Draw(image)
    font = get_font(300)
    w, h = image.size
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    x, y = (w-tw)//2, (h-th)//2
    glow = Image.new("RGBA", image.size, (0,0,0,0))
    glow_draw = ImageDraw.Draw(glow)
    for offset in range(20, 0, -4):
        glow_draw.text((x,y), text, font=font, fill=(0,255,255,160), stroke_width=offset)
    image.paste(glow.filter(ImageFilter.GaussianBlur(12)), (0,0), glow)
    draw.text((x,y), text, font=font, fill=(255,255,255,255), stroke_width=3)

def create_collage(media_type):
    paths = get_tmdb_data(media_type)
    if not paths: return None
    posters = []
    for path in paths:
        try:
            r = requests.get(IMG_BASE_URL+path, timeout=20)
            img = Image.open(BytesIO(r.content)).convert('RGBA')
            posters.append(ImageOps.fit(img, (TARGET_W, TARGET_H), Image.Resampling.LANCZOS))
        except: continue
    if not posters: return None
    canvas = Image.new('RGBA', (TARGET_W*5, TARGET_H*2), (0,0,0,0))
    for i, p in enumerate(posters):
        canvas.paste(p, ((i%5)*TARGET_W, (i//5)*TARGET_H))
    draw_neon_label(canvas, "MOVIES" if media_type=="movies" else "TV SHOWS")
    mask = Image.new('L', canvas.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0,0)+canvas.size, radius=60, fill=255)
    canvas.putalpha(mask)
    return canvas

def upload_to_jf(image_obj, item_id):
    if image_obj is None: return
    buffer = BytesIO()
    image_obj.convert("RGB").save(buffer, format='JPEG', quality=80)
    
    # Кодуємо в Base64
    img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    # URL ендпоінт для прямого завантаження зображення
    url = f"{JF_HOST.rstrip('/')}{JF_BASE_URL}/Items/{item_id}/Images/Primary"
    
    # КЛЮЧОВИЙ МОМЕНТ: 
    # Ми шлемо Base64 рядок як звичайний текст, але Jellyfin зрозуміє його через заголовок
    headers = {
        "X-Emby-Token": JF_API_KEY,
        "Content-Type": "text/plain" # Jellyfin часто приймає Base64 як чистий текст
    }
    
    try:
        res = requests.post(url, headers=headers, data=img_b64, timeout=60)
        
        # Якщо 400 продовжується, спробуємо змінити Content-Type на image/jpeg навіть для Base64
        if res.status_code == 400:
            headers["Content-Type"] = "image/jpeg"
            res = requests.post(url, headers=headers, data=img_b64, timeout=60)

        if res.status_code in [200, 204]:
            print(f"[{datetime.datetime.now()}] Успішно оновлено ID: {item_id}")
        else:
            print(f"Помилка {item_id}: {res.status_code}. {res.text}")
    except Exception as e:
        print(f"Помилка підключення: {e}")

def job():
    print(f"\n--- Старт: {datetime.datetime.now()} ---")
    upload_to_jf(create_collage("movies"), MOVIES_ITEM_ID)
    upload_to_jf(create_collage("tv_shows"), TV_ITEM_ID)
    print("--- Завершено ---")

job()
schedule.every().monday.at("08:00").do(job)
while True:
    schedule.run_pending()
    time.sleep(60)
