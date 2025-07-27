"""
motor.py
Processo separado que recebe caminhos por IPC,
move os ficheiros para as pastas corretas e
monitoriza uma pasta em tempo real (opcional).
"""
from __future__ import annotations
import os, shutil, json, datetime, pathlib, threading, socketserver, struct, mimetypes
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

CATEGORIAS = {
    "Imagens":      [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg", ".ico", ".tiff", ".raw"],
    "Vídeos":       [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp", ".mpg", ".mpeg"],
    "Documentos":   [".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".pages", ".epub", ".mobi"],
    "FolhasCálculo":[".xls", ".xlsx", ".ods", ".csv", ".numbers"],
    "Apresentações":[".ppt", ".pptx", ".odp", ".key"],
    "Música":       [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus", ".aiff"],
    "Arquivos":     [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".bz2", ".xz", ".iso"],
    "Código":       [".py", ".js", ".html", ".css", ".java", ".cpp", ".c", ".go", ".rs", ".php", ".rb", ".ts", ".jsx", "..vue", ".json", ".xml", ".yaml", ".yml"],
    "Fontes":       [".ttf", ".otf", ".woff", ".woff2", ".eot"],
    "Executáveis":  [".exe", ".msi", ".deb", ".dmg", ".appimage", ".pkg", ".rpm"]
}

def categoria_do(caminho: pathlib.Path) -> str | None:
    ext = caminho.suffix.lower()
    for cat, exts in CATEGORIAS.items():
        if ext in exts:
            return cat
    return None

def novo_nome(original: pathlib.Path) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{original.name}"

def mover_ficheiro(origem: pathlib.Path, definições: dict) -> tuple[str, str]:
    cat = categoria_do(origem)
    if not cat:
        return ("❓ SemCategoria", str(origem))

    base = pathlib.Path(definições["pasta_base"]).expanduser()
    destino_dir = base / cat
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / novo_nome(origem)

    if definições["duplicados"] == "renomear":
        contador = 1
        while destino.exists():
            destino = destino_dir / f"{destino.stem}_{contador}{destino.suffix}"
            contador += 1
    elif definições["duplicados"] == "ignorar" and destino.exists():
        return ("⏭️ Ignorado (duplicado)", str(destino))

    shutil.move(str(origem), str(destino))
    return (cat, str(destino))

# --------- IPC ---------
class ServidorIPC(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

class ManipuladorIPC(socketserver.BaseRequestHandler):
    def handle(self):
        tamanho = struct.unpack(">I", self.request.recv(4))[0]
        dados = self.request.recv(tamanho).decode()
        caminho = pathlib.Path(dados)
        with trinco:
            cat, dest = mover_ficheiro(caminho, definições)
        resposta = dest.encode()
        self.request.sendall(struct.pack(">I", len(resposta)) + resposta)

trinco = threading.Lock()
definições = json.load(open("settings.json"))

# --------- Monitorização em tempo real ---------
class Monitor(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            with trinco:
                mover_ficheiro(pathlib.Path(event.src_path), definições)

def iniciar_monitor(caminho: pathlib.Path):
    obs = Observer()
    obs.schedule(Monitor(), str(caminho), recursive=False)
    obs.start()

if __name__ == "__main__":
    HOST, PORTA = "127.0.0.1", 65432
    with ServidorIPC((HOST, PORTA), ManipuladorIPC) as servidor:
        pasta_vigiada = pathlib.Path(definições.get("pasta_vigiada", "")).expanduser()
        if pasta_vigiada.exists():
            iniciar_monitor(pasta_vigiada)
        servidor.serve_forever()