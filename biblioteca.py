import os
import json
import io
from urllib.parse import quote

import fitz
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.getcwd()
PDF_DIR = BASE_DIR
ANCHO = 332
ALTO = 443
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)


# --- Funciones ---


def buscar_pdfs_en_root(base_dir):
    """Busca PDFs en la carpeta raíz y devuelve lista de tuplas (ruta, carpeta, archivo)."""
    pdfs = []
    for f in os.listdir(base_dir):
        if f.lower().endswith(".pdf"):
            pdfs.append((os.path.join(base_dir, f), ".", f))
    return pdfs


def sanitizar_nombre(nombre):
    """Sanitiza el nombre reemplazando guiones y guiones bajos por espacios y capitalizando."""
    nombre_sin_ext = os.path.splitext(nombre)[0]
    nombre_limpio = nombre_sin_ext.replace("-", " ").replace("_", " ")
    if nombre_limpio:
        nombre_limpio = nombre_limpio[0].upper() + nombre_limpio[1:]
    return nombre_limpio


def crear_logo_pdf(ruta_salida=os.path.join(STATIC_DIR, "logo.webp"), tamaño=(256, 256)):
    """Crea un logo PDF en formato WEBP."""
    fondo_rojo = (220, 20, 60)
    texto_blanco = (255, 255, 255)

    img = Image.new("RGB", tamaño, fondo_rojo)
    draw = ImageDraw.Draw(img)

    try:
        fuente = ImageFont.truetype(
            os.path.join(BASE_DIR, "arialbd.ttf"),
            size=int(tamaño[1] * 0.4)
        )
    except OSError:
        fuente = ImageFont.load_default()

    texto = "PDF"
    bbox = draw.textbbox((0, 0), texto, font=fuente)
    texto_ancho = bbox[2] - bbox[0]
    texto_alto = bbox[3] - bbox[1]
    posicion = ((tamaño[0] - texto_ancho) // 2, (tamaño[1] - texto_alto) // 2)

    draw.text(posicion, texto, fill=texto_blanco, font=fuente)
    img.save(ruta_salida, "WEBP")
    print(f"Logo PDF creado: {ruta_salida}")


def crear_favicon():
    """Crea favicon.ico a partir del logo."""
    ruta_logo = os.path.join(STATIC_DIR, "logo.webp")
    ruta_fav = os.path.join(STATIC_DIR, "favicon.ico")
    img = Image.open(ruta_logo).convert("RGBA")
    img = img.resize((128, 128), Image.LANCZOS)
    img.save(ruta_fav, format="ICO")


def crear_manifest():
    """Crea el archivo site.webmanifest usando el nombre del repo."""
    repo_name = os.path.basename(os.getcwd())
    repo = sanitizar_nombre(repo_name)
    manifest = {
        "name": repo,
        "short_name": repo + " App",
        "start_url": "../index.html",
        "display": "standalone",
        "background_color": "#dc143c",
        "theme_color": "#dc143c",
        "description": "Visualizador de PDFs con miniaturas",
        "icons": [
            {"src": "logo.webp", "sizes": "256x256", "type": "image/webp"},
            {
                "src": "favicon.ico",
                "sizes": "128x128 64x64 32x32 24x24 16x16",
                "type": "image/x-icon",
            },
        ],
    }
    ruta = os.path.join(STATIC_DIR, "site.webmanifest")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)


def crear_service_worker(pdfs):
    """Crea el service-worker.js para caché de la PWA."""
    urls = ["./", "logo.webp", "favicon.ico", "site.webmanifest"]
    
    for _, _, archivo in pdfs:
        base = os.path.splitext(archivo)[0]
        miniatura = quote(f"{base}.webp")
        pdf_url = quote(f"{archivo}")
        urls.append(pdf_url)
        urls.append(miniatura)
        
    contenido = f"""
const CACHE_NAME = "revistas-cache-v1";
const urlsToCache = {urls};

self.addEventListener("install", event => {{
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
}});

self.addEventListener("activate", event => {{
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.map(key => {{
        if (key !== CACHE_NAME) {{
          return caches.delete(key);
        }}
      }}))
    )
  );
}});

self.addEventListener("fetch", event => {{
  event.respondWith(
    caches.match(event.request).then(response =>
      response || fetch(event.request).catch(() =>
        new Response("No hay conexión y el recurso no está en caché.", {{
          headers: {{ "Content-Type": "text/plain" }}
        }})
      )
    )
  );
}});
"""
    ruta_sw = os.path.join(STATIC_DIR, "service-worker.js")
    with open(ruta_sw, "w", encoding="utf-8") as f:
        f.write(contenido.strip())


def extraer_miniaturas(pdfs):
    """Extrae la primera página de cada PDF y crea miniaturas WEBP."""
    for ruta_pdf, _, archivo in pdfs:
        base = os.path.splitext(archivo)[0]
        salida_miniatura = os.path.join(STATIC_DIR, base + ".webp")
        if os.path.exists(salida_miniatura):
            continue
            
        try:
            with fitz.open(ruta_pdf) as doc:
                pagina = doc[0]
                pix = pagina.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72))
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                img_red = img.resize((ANCHO, ALTO), Image.LANCZOS)
                img_red.save(salida_miniatura, "WEBP", quality=80, lossless=True)
        except Exception as e:
            print(f"Error en {archivo}: {e}")


def generar_html(pdfs):
    """Genera el index.html con las miniaturas y títulos de los PDFs."""
    folder_name = os.path.basename(os.getcwd())

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{folder_name}</title>
    <link rel="icon" type="image/x-icon" href="static/favicon.ico">
    <link rel="manifest" href="static/site.webmanifest">
    <script src="static/service-worker.js"></script>
    <style>
        html, body {{
            margin: 0;
            padding: 0;
            height: 100%;
            overflow-x: hidden;
            font-family: Arial, sans-serif;
        }}
        
        #fondo {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
        }}
        
        #logo {{
            margin: 20px auto;
            width: 256px;
            height: auto;
            text-align: center;
            border-radius: 30px;
            overflow: hidden;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }}
        
        #logo img {{
            display: block;
            width: 100%;
            height: auto;
        }}
        
        .pdfs-container {{
            display: grid;
            gap: 20px;
            justify-items: center;
            padding: 20px;
        }}

        .pdfs-container.few-1 {{ grid-template-columns: 1fr; max-width: 400px; margin: 0 auto; }}
        .pdfs-container.few-2 {{ grid-template-columns: repeat(2, 1fr); max-width: 700px; margin: 0 auto; }}
        .pdfs-container:not(.few-1):not(.few-2) {{ grid-template-columns: repeat(3, 1fr); max-width: 100%; margin: 0 auto; }}


        .pdf-container {{
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            background: #fff;
            transition: transform 0.2s;
            width: 100%;      /* llena la celda del grid */
            max-width: 332px; /* el ancho de la miniatura */
        }}
        
        .pdf-container:hover {{
            transform: scale(1.05);
        }}
        
        .pdf-thumbnail {{
            width: 100%;
            height: auto;
            cursor: pointer;
            display: block;
        }}

        .pdf-row {{
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
        }}

        .pdf-row-few {{
            justify-content: center;
        }}
        
        .pdf-title {{
            text-align:center;
            font-size: 14px;
            font-weight: bold;
            color: #333;
            margin-top: 5px;
            margin-bottom: 10px;
            box-sizing: border-box;
        }}
        
        @media (max-width: 768px) {{
            #pdfs-container {{
                grid-template-columns: 1fr 1fr;
            }}
        }}
        
        @media (max-width: 480px) {{
            #pdfs-container {{
                grid-template-columns: 1fr;
            }}
        }}
        
        footer {{
            text-align: center;
            margin-top: 30px;
            padding: 15px 0;
            color: #555;
            font-size: 12px;
        }}
        
        footer img {{
            max-width: 50px;
            margin-bottom: 5px;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }}

        footer p {{
            margin: 0;
            font-size: 12px;
            color: #555;
        }}
        
        h2 {{
            background-color: rgba(255, 255, 255, 0.8); 
            color: #333;                             
            text-align: center;                        
            padding: 10px 0;                            
            margin: 20px 40px;                      
            border-radius: 10px;                    
            width: calc(100% - 80px);                               
            box-sizing: border-box;                       
        }}
    </style>
    <div id="fondo"></div>
    <script>
    const fondo = document.getElementById('fondo');
    let hue = 0;
    function animateBackground() {{
        hue = (hue + 0.5) % 360;
        fondo.style.background = `linear-gradient(135deg, hsl(${{hue}}, 70%, 80%), hsl(${{(hue+60)%360}}, 70%, 80%))`;
        requestAnimationFrame(animateBackground);
    }}
    animateBackground();
</script>
    <script>
    if ('serviceWorker' in navigator) {{
      window.addEventListener('load', function() {{
        navigator.serviceWorker.register("static/service-worker.js").then(function(registration) {{
          console.log('ServiceWorker registration successful with scope: ', registration.scope);
        }}, function(err) {{
          console.log('ServiceWorker registration failed: ', err);
        }});
      }});
    }}
  </script>
</head>
<body>
    <div id="logo">
        <img src="static/logo.webp" alt="{folder_name}">
    </div>
    <div class="pdfs-container">
"""

    for _, _, archivo in pdfs:
        base = os.path.splitext(archivo)[0]
        titulo_limpio = sanitizar_nombre(base)
        ruta_miniatura = quote(f"static/{base}.webp")
        ruta_pdf = quote(f"{archivo}")
        html += f"""
        <div class="pdf-container">
            <img src="{ruta_miniatura}" class="pdf-thumbnail" onclick="window.open('{ruta_pdf}', '_blank')">
            <p class="pdf-title">{titulo_limpio}</p>
        </div>
"""

    html += """
    </div>
</body>
</html>
"""
    ruta_index = os.path.join(BASE_DIR, "index.html")
    with open(ruta_index, "w", encoding="utf-8") as f:
        f.write(html)


# --- Ejecución ---

pdf_files = buscar_pdfs_en_root(PDF_DIR)
extraer_miniaturas(pdf_files)
crear_logo_pdf()
crear_favicon()
crear_manifest()
crear_service_worker(pdf_files)
generar_html(pdf_files)

print("✅ Sitio PWA estático generado en '/' listo para GitHub Pages.")
