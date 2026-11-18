"""Prueba de humo de extremo a extremo por HTTP contra un servidor Uvicorn real.

Uso:
    python scripts/smoke_test.py                 # usa Faster-Whisper real si está instalado
    python scripts/smoke_test.py --fake-whisper  # transcripción simulada (rápido, sin descargar modelos)

Genera un video sintético con FFmpeg, lo sube con derechos aprobados, espera el análisis,
edita subtítulos, exporta un Short, verifica control de calidad, descargas y bloqueos de derechos.
Usa un directorio de datos temporal: no toca tus proyectos.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile, threading, time, urllib.error, urllib.request, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--fake-whisper", action="store_true")
ap.add_argument("--port", type=int, default=8765)
args = ap.parse_args()
WORK = Path(tempfile.mkdtemp(prefix="elmariana_smoke_"))
os.environ["ELMARIANA_DATA_DIR"] = str(WORK / "data")
sys.path.insert(0, str(ROOT))

from app.services import transcribe as T

USE_FAKE = args.fake_whisper or not T.whisper_available()
if not USE_FAKE and not shutil.which("espeak-ng"):
    print("Aviso: falta espeak-ng (sudo apt-get install -y espeak-ng); sin voz no se puede probar Whisper real.")
    USE_FAKE = True

LINES = ["Hola chat, bienvenidos al stream de hoy.", "Hoy vamos a probar el nuevo mapa.", "Miren esto, está muy raro.",
         "Creo que por aquí hay algo escondido.", "Espera, espera, ¿qué fue eso?", "¡No manches, jajaja, qué susto!",
         "No puede ser, me muero de risa.", "Bueno, sigamos con la partida.", "Vamos a revisar el inventario.",
         "Aquí tengo unas pociones y una espada.", "¿Ustedes qué harían en mi lugar?", "Escriban en el chat."]

print("Generando video de prueba…")
if USE_FAKE:
    DUR = 90.0
    audio_in = ["-f", "lavfi", "-i", "sine=f=200:d=90"]
    audio_filter = "volume='if(between(t,40,42),3.0,0.2)':eval=frame"
else:
    # Voz sintética en español para que Faster-Whisper real tenga algo que transcribir.
    speech = WORK / "voz.wav"
    subprocess.run(["espeak-ng", "-v", "es", "-s", "145", "-g", "8", "-w", str(speech), " ".join(LINES * 3)], check=True)
    DUR = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(speech)], capture_output=True, text=True, check=True).stdout) + 2
    peak = round(DUR * 0.45, 1)
    audio_in = ["-i", str(speech)]
    audio_filter = f"apad,volume='if(between(t,{peak},{peak + 3}),2.5,1)':eval=frame"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=s=1280x720:r=30:d={DUR}", *audio_in,
                "-af", audio_filter, "-t", str(DUR), "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
                str(WORK / "long.mp4")], check=True)
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(WORK / "long.mp4"), "-c", "copy", str(WORK / "long.mkv")], check=True)


def fake(audio, language="auto", model_size=None, duration=None, on_progress=None):
    segs=[]; t=1.0; k=0
    lines=["Hola chat, bienvenidos al stream de hoy.","Hoy vamos a probar el nuevo mapa.","Miren esto, está muy raro.",
           "Creo que por aquí hay algo escondido.","Espera, espera, ¿qué fue eso?","¡No manches, jajaja, qué susto!",
           "No puede ser, me muero de risa.","Bueno, sigamos con la partida.","Vamos a revisar el inventario.",
           "Aquí tengo unas pociones y una espada.","¿Ustedes qué harían en mi lugar?","Escriban en el chat."]
    while t < 86:
        text=lines[k%len(lines)]; ws=text.split(); words=[]; tt=t
        for w in ws: words.append({"w":w,"start":round(tt,2),"end":round(tt+0.32,2),"p":0.9 if w!="escondido." else 0.3}); tt+=0.42
        segs.append({"start":t,"end":round(tt,2),"text":text,"words":words}); t=tt+(1.6 if k%4==3 else 0.35); k+=1
        if on_progress: on_progress(min(t/(duration or 90),1))
    return {"language":"es","language_probability":0.99,"model":"fake","segments":segs}
if USE_FAKE:
    print('Usando transcripción simulada')
    T.transcribe = fake

import uvicorn
from app.main import app
srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="warning"))
threading.Thread(target=srv.run, daemon=True).start()
time.sleep(1.5)
B=f"http://127.0.0.1:{args.port}"

def req(method, path, data=None, headers=None, raw=False):
    r = urllib.request.Request(B+path, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(r, timeout=600) as resp:
            body = resp.read(); return resp.status, (body if raw else (json.loads(body) if body else None)), dict(resp.headers)
    except urllib.error.HTTPError as e:
        body=e.read(); return e.code, (json.loads(body) if body[:1]==b"{" else body), dict(e.headers)

def multipart(fields, fpath):
    bnd = uuid.uuid4().hex; out=b""
    for k,v in fields.items():
        out += f"--{bnd}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    out += f"--{bnd}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{os.path.basename(fpath)}\"\r\nContent-Type: video/mp4\r\n\r\n".encode()
    out += open(fpath,"rb").read() + f"\r\n--{bnd}--\r\n".encode()
    return out, {"Content-Type": f"multipart/form-data; boundary={bnd}"}

results=[]
def check(name, cond, info=""):
    results.append((name, bool(cond))); print(("PASS " if cond else "FAIL ")+name, info if not cond else "")

s,h,_ = req("GET","/api/health"); check("health", s==200 and h["ffmpeg"], h)
s,_,_ = req("GET","/", raw=True); check("index.html servido", s==200)
s,_,_ = req("GET","/static/app.js", raw=True); check("app.js servido", s==200)

ok_rights = dict(name="Prueba", language="es", whisper_model="base", source_description="Stream propio de prueba",
                 rights_holder="ElMariana", creator_name="ElMariana", permission_type="own", evidence="Contenido propio",
                 third_party_music="no", third_party_footage="no", confirmed="true")
d,hd = multipart({**ok_rights, "confirmed":"false"}, str(WORK/"long.mp4"))
s,b,_ = req("POST","/api/projects", d, hd); check("subida sin confirmar derechos -> 403", s==403, (s,b))
open(str(WORK/"bad.avi"),"wb").write(b"x"*100)
d,hd = multipart(ok_rights, str(WORK/"bad.avi")); s,b,_ = req("POST","/api/projects", d, hd); check("formato .avi rechazado", s==400, (s,b))
open(str(WORK/"fake.mp4"),"wb").write(b"no es video"*100)
d,hd = multipart(ok_rights, str(WORK/"fake.mp4")); s,b,_ = req("POST","/api/projects", d, hd); check("mp4 corrupto rechazado", s==400, (s,b))

# Subida por partes (como la interfaz; evita el 413 del túnel de Codespaces)
src_file = WORK/"long.mkv"; size = src_file.stat().st_size
s,init,_ = req("POST","/api/uploads", json.dumps({"filename":"long.mkv","size":size}).encode(), {"Content-Type":"application/json"})
check("subida por partes: inicio", s==201, (s,init)); uid=init["upload_id"]
CH = 4*1024*1024; off = 0; dup_ok = True
with open(src_file,"rb") as fh:
    while off < size:
        fh.seek(off); data = fh.read(CH)
        s,r,_ = req("PUT",f"/api/uploads/{uid}?offset={off}", data, {"Content-Type":"application/octet-stream"})
        if s != 200: break
        if off == 0:  # reintento del mismo trozo: no debe duplicarse
            s2,r2,_ = req("PUT",f"/api/uploads/{uid}?offset=0", data, {"Content-Type":"application/octet-stream"})
            dup_ok = s2==200 and r2["received"]==len(data)
        off = r["received"]
check("subida por partes: todos los trozos", off==size, (off,size))
check("subida por partes: reintento sin duplicar", dup_ok)
fields = {**ok_rights, "upload_id": uid}
bnd = uuid.uuid4().hex
body = b"".join(f"--{bnd}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k,v in fields.items()) + f"--{bnd}--\r\n".encode()
s,p,_ = req("POST","/api/projects", body, {"Content-Type": f"multipart/form-data; boundary={bnd}"})
check("subida MKV aprobada -> 201", s==201, (s,p)); pid=p["id"]
check("análisis FFmpeg (duración/resolución/audio)", abs(p["media"]["duration"]-DUR)<0.6 and p["media"]["width"]==1280 and p["media"]["has_audio"], p["media"])
t0=time.time()
while True:
    s,p,_=req("GET",f"/api/projects/{pid}")
    if p["status"] in ("ready","error") : break
    time.sleep(0.5)
check("procesamiento termina en ready", p["status"]=="ready", p["progress"]); print("  procesado en", round(time.time()-t0,1),"s")
check("se generó proxy de vista previa para MKV", os.path.exists(str(WORK/"data"/"projects"/pid/"preview.mp4")))
clips=p["clips"]; check("hay clips candidatos", len(clips)>=1, len(clips))
for c in clips[:5]: print("   ", c["id"], c["score"], c["start"], c["end"], "|", c["title"], "|", c["reasons"][:2])
if not clips:
    print("\nNo se detectaron clips: la transcripción no tiene habla suficiente.", p.get("progress"))
    srv.should_exit = True; shutil.rmtree(WORK, ignore_errors=True); sys.exit(1)
c=clips[0]
check("clip con título, inicio, fin y puntuación", c["title"] and c["end"]>c["start"] and 0<=c["score"]<=100)
check("duraciones 20-60 s", all(19<=x["duration"]<=61 for x in clips), [x["duration"] for x in clips])
check("SEO: 3 títulos, descripción, hashtags", len(c["seo"]["titles"])>=2 and c["seo"]["description"] and "#shorts" in c["seo"]["hashtags"], c["seo"])
s,body,hh = req("GET",f"/api/projects/{pid}/media", headers={"Range":"bytes=0-1023"}, raw=True)
check("vista previa con Range 206", s==206 and len(body)==1024 and hh.get("content-range","").startswith("bytes 0-1023/"), (s,hh))
s,body,_=req("GET",f"/api/projects/{pid}/clips/{c['id']}/thumbnail", raw=True); check("miniatura", s==200 and body[:2]==b"\xff\xd8")
check("portada generada al analizar", all(x.get("cover") for x in clips), [x.get("cover") for x in clips][:2])
s,body,_=req("GET",f"/api/projects/{pid}/clips/{c['id']}/cover", raw=True)
open(str(WORK/"cover.jpg"),"wb").write(body if isinstance(body,bytes) else b"")
from app.services.media import probe as _probe
check("portada 1080x1920 JPG < 2 MB", s==200 and body[:2]==b"\xff\xd8" and len(body)<2*1024*1024
      and (_probe(str(WORK/"cover.jpg"))["width"], _probe(str(WORK/"cover.jpg"))["height"])==(1080,1920))
s,cc2,_=req("POST",f"/api/projects/{pid}/clips/{c['id']}/cover", json.dumps({"text":"Texto de prueba","at":c["start"]+3}).encode(), {"Content-Type":"application/json"})
check("regenerar portada con texto y fotograma", s==200 and cc2["cover"]["text"]=="Texto de prueba" and abs(cc2["cover"]["at"]-(c["start"]+3))<0.05, (s,cc2.get("cover") if isinstance(cc2,dict) else cc2))
s,_,_=req("GET",f"/api/projects/{pid}/clips/{c['id']}/cover?download=true", raw=True); check("descargar portada (derechos APPROVED)", s==200)
s,cd,_=req("GET",f"/api/projects/{pid}/clips/{c['id']}"); words=cd["subtitle_words"]; check("palabras del clip", len(words)>10)
words[0]["w"]="EDITADO"; words[1]["hl"]=True; words[2]["w"]=""
s,cu,_=req("PUT",f"/api/projects/{pid}/clips/{c['id']}", json.dumps({"words":words,"title":"Mi título"}).encode(), {"Content-Type":"application/json"})
check("editor de subtítulos guarda", s==200 and cu["words"][0]["w"]=="EDITADO" and len(cu["words"])==len(words)-1 and cu["title"]=="Mi título", (s,cu if s!=200 else ""))
s,b,_=req("PUT",f"/api/projects/{pid}/clips/{c['id']}", json.dumps({"start":10,"end":11}).encode(), {"Content-Type":"application/json"}); check("tiempos inválidos -> 400", s==400)
s,b,_=req("POST",f"/api/projects/{pid}/clips/{c['id']}/render", json.dumps({"layout":"auto","zoom":"suave","subtitles":True,"remove_pauses":True}).encode(), {"Content-Type":"application/json"})
check("render en cola 202", s==202, (s,b))
t0=time.time()
while True:
    s,cc,_=req("GET",f"/api/projects/{pid}/clips/{c['id']}")
    if cc["status"] in ("exported","qc_failed","error"): break
    time.sleep(0.5)
print("  render en", round(time.time()-t0,1), "s; estado", cc["status"])
if cc.get("error"): print(cc["error"])
qc=cc.get("qc") or {}
for pr in qc.get("problems",[]): print("   QC", pr["level"], pr["area"], pr["message"])
check("exportado con QC PASS", cc["status"]=="exported" and qc.get("status")=="PASS")
s,body,hh=req("GET",f"/api/projects/{pid}/clips/{c['id']}/download", raw=True)
check("descarga MP4", s==200 and "attachment" in hh.get("content-disposition",""), (s,hh))
if s != 200:
    print("\nNo se pudo exportar el clip; se detiene la prueba.", cc.get("error") or "")
    srv.should_exit = True; shutil.rmtree(WORK, ignore_errors=True); sys.exit(1)
open(str(WORK/"dl.mp4"),"wb").write(body)
from app.services.media import probe
pi=probe(str(WORK/"dl.mp4")); check("MP4 final 1080x1920 h264/aac", pi["width"]==1080 and pi["height"]==1920 and pi["video_codec"]=="h264" and pi["audio_codec"]=="aac", pi)
s,body,_=req("GET",f"/api/projects/{pid}/clips/{c['id']}/download?kind=srt", raw=True); check("descarga SRT", s==200 and b"-->" in body and b"EDITADO" in body)
s,body,_=req("GET",f"/api/projects/{pid}/clips/{c['id']}/download?kind=metadata", raw=True); check("descarga metadatos", s==200 and "DESCRIPCIÓN".encode() in body)
ass=open(str(WORK/"data"/"projects"/pid/"clips"/(c["id"]+".ass")),encoding="utf-8").read()
check("ASS: palabra editada y resaltados", "EDITADO" in ass and "\\c&H007AF03C&" in ass and "\\c&H0000E5FF&" in ass)
# derechos pasan a REVIEW -> descarga bloqueada
s,pp,_=req("PUT",f"/api/projects/{pid}/rights", json.dumps({**{k:v for k,v in ok_rights.items() if k not in ("name","language","whisper_model")},"confirmed":True,"third_party_music":"unknown"}).encode(), {"Content-Type":"application/json"})
check("derechos -> REVIEW REQUIRED", s==200 and pp["rights_review"]["status"]=="REVIEW REQUIRED", pp.get("rights_review") if s==200 else pp)
s,b,_=req("GET",f"/api/projects/{pid}/clips/{c['id']}/download"); check("descarga bloqueada por derechos -> 403", s==403, (s,b))
s,b,_=req("GET",f"/api/projects/{pid}/clips/{c['id']}/cover?download=true"); check("portada bloqueada por derechos -> 403", s==403, (s,b))
s,b,_=req("PUT",f"/api/projects/{pid}/clips/{c['id']}", json.dumps({"end": c["end"]-1}).encode(), {"Content-Type":"application/json"})
check("editar tras exportar marca 'edited'", s==200 and b["status"]=="edited", b)
s,lst,_=req("GET","/api/projects"); check("lista de proyectos", s==200 and lst[0]["id"]==pid)
s,_,_=req("DELETE",f"/api/projects/{pid}"); check("eliminar proyecto 204", s==204)
s,_,_=req("GET",f"/api/projects/{pid}"); check("proyecto eliminado -> 404", s==404)
s,_,_=req("GET",f"/api/projects/..%2Fetc"); check("ruta maliciosa -> 404", s==404)
print(f"\n{sum(r for _,r in results)}/{len(results)} comprobaciones OK")
srv.should_exit=True
shutil.rmtree(WORK, ignore_errors=True)
sys.exit(0 if all(r for _, r in results) else 1)
