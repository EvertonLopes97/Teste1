"""SERVIDOR 24h (06/nov): deixa no servidor do site o catcher de virais e a lista de produtos virais do Shop.

`python tools/viral/servidor.py [--pasta ~/DETTO/viral] [--shop ~/DETTO/shop] [--viral-min 20] [--shop-horas 6]`
 - a cada --viral-min min roda `viral.py` (acha vídeo explodindo, avisa no Telegram/Discord);
 - a cada --shop-horas h roda `shop/viral_shop.py` (lista produtos virais → produtos.txt / virais_shop.txt);
 - sem janela, sem painel, sem Playwright. Erro de um passo só vai para o registro e ele segue.
Para ligar no Linux: systemd (modelo em tools/viral/detto-viral.service). Variáveis: TELEGRAM_TOKEN, TELEGRAM_CHAT.
O vídeo baixado e o produtos.txt ficam NO SERVIDOR — para o PC usar, aponte a pasta pelo Drive/rsync.
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TOOLS = AQUI.parent


def log(m):
    print(f"{datetime.now():%d/%m %H:%M} {m}", flush=True)


def passo(cmd, tempo):
    try:
        r = subprocess.run([sys.executable, *cmd], capture_output=True, text=True, timeout=tempo,
                           encoding="utf-8", errors="replace")
        ult = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()][-3:]
        log(f"{Path(cmd[0]).name}: código {r.returncode} · " + " | ".join(ult)[:300])
    except Exception as e:   # noqa: BLE001
        log(f"{Path(cmd[0]).name}: falhou ({str(e)[:120]})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta", default=str(Path.home() / "DETTO" / "viral"))
    ap.add_argument("--shop", default=str(Path.home() / "DETTO" / "shop"))
    ap.add_argument("--viral-min", type=int, default=20)
    ap.add_argument("--shop-horas", type=float, default=6)
    a = ap.parse_args()
    Path(a.pasta).mkdir(parents=True, exist_ok=True)
    ult_shop = 0.0
    log(f"servidor no ar · virais a cada {a.viral_min} min · shop a cada {a.shop_horas} h")
    while True:
        passo([str(AQUI / "viral.py"), "--pasta", a.pasta], 900)
        if time.time() - ult_shop >= a.shop_horas * 3600:
            ult_shop = time.time()
            passo([str(TOOLS / "shop" / "viral_shop.py"), "--pasta", a.shop, "--quantos", "40"], 1200)
        time.sleep(max(60, a.viral_min * 60))


if __name__ == "__main__":
    main()
