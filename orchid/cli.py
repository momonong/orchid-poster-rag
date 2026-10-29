import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

from .config import Settings

REGIONS = {
    "flowers": [0.024, 0.296, 0.294, 0.391],
    "clue1": [0.308, 0.270, 0.689, 0.387],
    "clue2": [0.307, 0.448, 0.687, 0.700],
    "clue3": [0.313, 0.782, 0.682, 0.908],
    "intro": [0.023, 0.21, 0.295, 0.615],
    "methods": [0.023, 0.62, 0.295, 0.998],
    "discussion": [0.703, 0.209, 0.977, 0.384],
}
SOURCE_REGIONS = {**REGIONS, "clue1": [0.304, 0.239, 0.694, 0.401],
                  "clue2": [0.304, 0.406, 0.694, 0.723], "clue3": [0.304, 0.732, 0.694, 0.951]}


def prepare(settings, poster, paper, accept_reviewed=False):
    import pymupdf
    previous_path = settings.data / "sources.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else {}
    records = {}
    for name, value in (("poster", poster), ("paper", paper)):
        path = Path(value).resolve()
        if not path.is_relative_to(settings.root.resolve()) or not path.is_file():
            raise ValueError("原始 PDF 必須位於本專案內")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if name in previous and previous[name]["sha256"] != digest and not accept_reviewed:
            raise ValueError("來源 PDF 已變更。請先更新/校對 evidence.json，再使用 --accept-reviewed 登錄")
        records[name] = {"path": path.relative_to(settings.root).as_posix(), "sha256": digest}
    settings.cache.mkdir(parents=True, exist_ok=True)
    assets = settings.root / ".orchid" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(poster) as document:
        page = document[0]
        for name, rect in REGIONS.items():
            clip = pymupdf.Rect(rect[0] * page.rect.width, rect[1] * page.rect.height,
                                rect[2] * page.rect.width, rect[3] * page.rect.height)
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), clip=clip)
            from PIL import Image
            image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
            image.thumbnail((1400, 1400))
            image.save(assets / f"{name}.webp", "WEBP", quality=88)
        page.get_pixmap(matrix=pymupdf.Matrix(0.5, 0.5)).save(str(assets / "poster.png"))
        records["poster"]["regions"] = SOURCE_REGIONS
        records["poster"]["image_regions"] = REGIONS
    with pymupdf.open(paper) as document:
        # Export column-aware raw text for source audits, not automatic unchecked corpus ingestion.
        pages = []
        for number, page in enumerate(document):
            if number == 0:
                text = page.get_text()
            else:
                width, height = page.rect.width, page.rect.height
                text = "\n".join(page.get_text(clip=pymupdf.Rect(x, 35, x + width / 2, height - 25))
                                 for x in (0, width / 2))
            pages.append(f"--- PAGE {number + 1} ---\n{text}")
        (settings.cache / "paper-extracted.txt").write_text("\n\n".join(pages), encoding="utf-8")
        records["paper"]["pages"] = len(document)
        evidence_path = settings.data / "evidence.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        excerpt_map = json.loads((settings.data / "excerpt-map.json").read_text(encoding="utf-8"))
        for item in evidence:
            if item["id"] in excerpt_map:
                extracts, locators = [], []
                for page_number, block_id in excerpt_map[item["id"]]:
                    source_page = document[page_number - 1]
                    block = source_page.get_text("blocks")[block_id]
                    extracts.append(block[4].strip())
                    locators.append({"document": "paper", "page": page_number,
                        "rect": [round(v / (source_page.rect.width if i % 2 == 0 else source_page.rect.height), 5)
                                 for i, v in enumerate(block[:4])]})
                item["original_excerpt"] = "\n\n".join(extracts)
                item["locators"] = locators
                item["source_sha256"] = records["paper"]["sha256"]
    with pymupdf.open(poster) as document:
        page = document[0]
        selections = {"S01": ["intro", "clue1", "clue2", "clue3"], "S02": ["methods"],
                      "S03": ["clue2"], "S04": ["clue3", "discussion"]}
        for item in evidence:
            if item["id"] in selections:
                extracts, locators = [], []
                for section in selections[item["id"]]:
                    rect = SOURCE_REGIONS[section]
                    clip = pymupdf.Rect(rect[0] * page.rect.width, rect[1] * page.rect.height,
                                        rect[2] * page.rect.width, rect[3] * page.rect.height)
                    extracts.append(page.get_text(clip=clip).strip())
                    locators.append({"document": "poster", "page": 1, "section": section, "rect": rect})
                item["original_excerpt"] = "\n\n".join(extracts)
                item["locators"] = locators
                item["source_sha256"] = records["poster"]["sha256"]
            elif item["id"] == "C01":
                item["original_excerpt"] = ("Following publication of the original article [1], the authors identified errors in the numbering of figures due to the movement of Materials and Methods section at the end of the article. The current Figs. 2 and 3 need to be switched to the end of the article to be Figs. 10 and 11, and the correct Figs. 2, 3, 4, 5, 6, 7, 8 and 9 are the current Figs. 4, 5, 6, 7, 8, 9, 10 and 11.\n\nThe original article [1] has been corrected.")
                item["locators"] = [{"document": "correction", "section": "Correction notice"}]
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    records["correction"] = {"url": "https://link.springer.com/article/10.1186/s12870-024-05475-w",
                             "version": "2024-08-17", "verified": "2026-10-29"}
    previous_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print("已登錄原始 PDF 指紋並裁切真實海報圖材；請在語料變更後重建索引。")


def start(settings, port):
    import psutil
    state = settings.root / ".orchid" / "app.json"
    if state.exists():
        record = json.loads(state.read_text())
        if psutil.pid_exists(record["pid"]):
            raise ValueError("本專案已有記錄中的程序，請先執行 status 核對")
    instance = str(uuid.uuid4())
    log = settings.root / ".orchid" / "app.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"cwd": settings.root, "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    with log.open("ab") as stream:
        process = subprocess.Popen([sys.executable, "-m", "orchid.cli", "serve", "--port", str(port),
                                    "--instance", instance], stdout=stream, stderr=stream, **kwargs)
    state.write_text(json.dumps({"pid": process.pid, "instance": instance, "port": port}), encoding="utf-8")
    time.sleep(1)
    if process.poll() is not None:
        raise ValueError("應用程序已退出，請查看 .orchid/app.log")
    print(f"應用程序已建立 PID {process.pid}；就緒狀態請執行 orchid status，網址 http://127.0.0.1:{port}")


def stop(settings):
    import psutil
    state = settings.root / ".orchid" / "app.json"
    if not state.exists():
        print("沒有本專案建立的背景程序")
        return
    record = json.loads(state.read_text())
    try:
        process = psutil.Process(record["pid"])
        command = process.cmdline()
    except psutil.NoSuchProcess:
        state.unlink()
        print("登錄的應用程序已不存在；已清除過期紀錄")
        return
    if "orchid.cli" not in command or record["instance"] not in command:
        raise ValueError("PID 所屬程序已改變；拒絕停止")
    try:
        descendants = process.children(recursive=True)
    except psutil.NoSuchProcess:
        descendants = []
    children = []
    # Windows venv's launcher may create the actual Python server as its child.
    for child in descendants:
        try:
            child_command = child.cmdline()
            system_conhost = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32" / "conhost.exe"
            if os.name == "nt" and Path(child.exe()).resolve() == system_conhost.resolve():
                # Windows console helper is verified by exact executable path and process ancestry.
                # Let it close naturally with its owning Python process.
                continue
            if "orchid.cli" not in child_command or record["instance"] not in child_command:
                raise ValueError("背景程序包含無法核對的子程序；拒絕停止")
            children.append(child)
        except psutil.NoSuchProcess:
            continue
    for child in reversed(children):
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            continue
    try:
        process.terminate()
    except psutil.NoSuchProcess:
        pass
    _, alive = psutil.wait_procs([*children, process], timeout=10)
    if alive:
        raise ValueError("應用尚未退出；保留程序紀錄供人工核對")
    state.unlink()
    print("本專案應用程序已停止；模型與 ngrok 保持原狀")


def main():
    parser = argparse.ArgumentParser(description="蘭花海報本機導覽工具")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("serve", "start"):
        p = sub.add_parser(command)
        p.add_argument("--port", type=int, default=8000)
        p.add_argument("--instance", default="foreground", help=argparse.SUPPRESS)
    sub.add_parser("stop")
    p = sub.add_parser("status")
    p.add_argument("--port", type=int, default=8000)
    p = sub.add_parser("prepare")
    p.add_argument("--poster", default="理學院研究日.pdf")
    p.add_argument("--paper", default="s12870-024-05305-z.pdf")
    p.add_argument("--accept-reviewed", action="store_true")
    p = sub.add_parser("index")
    p.add_argument("--download", action="store_true")
    p.add_argument("--tokenizer-dir", help="已核對為目標固定 revision 的本機 Qwen tokenizer 目錄")
    p = sub.add_parser("eval")
    p.add_argument("--mode", choices=["retrieval", "live"], default="retrieval")
    p.add_argument("--limit", type=int, default=21)
    p.add_argument("--language", choices=["en", "zh-TW"], default="zh-TW",
                   help="回答語言；既有中文 golden 題組預設 zh-TW")
    p = sub.add_parser("qr")
    p.add_argument("--url")
    p.add_argument("--output", default="output/guide-qr.png")
    args = parser.parse_args()
    settings = Settings()
    try:
        if args.command == "prepare":
            prepare(settings, args.poster, args.paper, args.accept_reviewed)
        elif args.command == "index":
            from .retrieval import build_index
            from .token_budget import prepare_tokenizer
            if args.download or args.tokenizer_dir:
                prepare_tokenizer(settings, args.tokenizer_dir)
            print(json.dumps(build_index(settings, args.download), ensure_ascii=False))
        elif args.command == "serve":
            import uvicorn

            from .app import create_app
            uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port, access_log=False)
        elif args.command == "start":
            start(settings, args.port)
        elif args.command == "stop":
            stop(settings)
        elif args.command == "status":
            import httpx
            print(json.dumps(httpx.get(f"http://127.0.0.1:{args.port}/api/health", timeout=8,
                                       trust_env=False).json(), ensure_ascii=False, indent=2))
        elif args.command == "qr":
            import qrcode
            url = args.url or settings.public_url
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
                raise ValueError("QR 只接受實際已配置的 HTTPS 公開網址")
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            qrcode.make(url).save(path)
            print(f"QR 已產生：{path.resolve()}；內容：{url}（可達性須另外核對）")
        elif args.command == "eval":
            from .evaluation import evaluate
            evaluate(settings, args.mode, args.limit, args.language)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"未完成：{exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
