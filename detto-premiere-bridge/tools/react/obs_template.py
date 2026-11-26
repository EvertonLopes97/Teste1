# -*- coding: utf-8 -*-
"""Template de LIVE do DETTO REAGE para o OBS (o mesmo visual da edição de react).

    python tools/react/obs_template.py [--pasta C:/Users/guebe/Teste1/obs]

Gera na pasta `obs/` (raiz do projeto):
  fundo_horizontal.png / fundo_vertical.png   fundo com moldura do vídeo, faixa e painel @detto.galo
  moldura_camera_*.png                         borda amarela da sua câmera (transparente)
  pausa_*.png                                  selo por cima da câmera em tela cheia (na pausa)
  DETTO_REAGE_cenas.json                       coleção de cenas para importar no OBS
  POSICOES.txt                                 onde vai cada fonte, se preferir montar à mão
Usa a sua caricatura/patrocínio se existirem em E:/DETTO/marca (caricatura.png, patrocinio.png).
"""
import argparse
import json
import os
import sys
import uuid
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import react as R  # noqa: E402

RAIZ = AQUI.parents[2]


def moldura_png(L, rect, esp=10):
    img = Image.new("RGBA", (L["W"], L["H"]), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = rect
    for k in range(esp):
        c = tuple(int(R.BRANCO[i] + (R.AMARELO[i] - R.BRANCO[i]) * k / max(1, esp - 1)) for i in range(3))
        d.rectangle((x0 - esp + k, y0 - esp + k, x1 + esp - k, y1 + esp - k), outline=c + (255,), width=1)
    return img


def pausa_png(L):
    """Pausa: você em tela cheia; só um selo discreto (canto de baixo) e o @ no alto."""
    W, H = L["W"], L["H"]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    vert = H > W
    s = 1.0 if not vert else 1.15
    bx, by = (40, H - 150) if not vert else (40, H - 420)
    f1, f2 = R.fonte("Anton-Regular.ttf", int(52 * s)), R.fonte("Inter-ExtraBold.otf", int(30 * s))
    w1 = int(300 * s)
    d.rectangle((bx, by, bx + w1, by + int(80 * s)), fill=R.PRETO + (255,))
    d.text((bx + w1 / 2, by + 40 * s), "DETTO REAGE", font=f1, fill=R.AMARELO, anchor="mm")
    d.rectangle((bx + w1, by, bx + w1 + int(260 * s), by + int(80 * s)), fill=R.AMARELO + (255,))
    d.text((bx + w1 + 130 * s, by + 40 * s), "@detto.galo", font=f2, fill=R.PRETO, anchor="mm")
    # borda fina amarela na tela toda
    d.rectangle((0, 0, W - 1, H - 1), outline=R.AMARELO + (255,), width=8)
    return img


def item(nome, src_uuid, idx, x, y, w=None, h=None, cobre=False):
    it = {
        "name": nome, "source_uuid": src_uuid, "visible": True, "locked": False, "rot": 0.0,
        "pos": {"x": float(x), "y": float(y)}, "scale": {"x": 1.0, "y": 1.0}, "align": 5,
        "bounds_type": 0, "bounds_align": 0, "bounds_crop": False, "bounds": {"x": 0.0, "y": 0.0},
        "crop_left": 0, "crop_top": 0, "crop_right": 0, "crop_bottom": 0, "id": idx, "group_item_backup": False,
        "scale_filter": "disable", "blend_method": "default", "blend_type": "normal",
    }
    if w is not None:
        # 2 = cabe dentro (vídeo inteiro, sem cortar); 3 = cobre e corta o que sobra (câmera)
        it.update({"bounds_type": 3 if cobre else 2, "bounds_crop": bool(cobre), "bounds": {"x": float(w), "y": float(h)}})
    return it


def fonte_obs(nome, sid, settings):
    return {"id": sid, "versioned_id": sid, "name": nome, "uuid": str(uuid.uuid4()), "settings": settings,
            "enabled": True, "flags": 0, "mixers": 255 if sid in ("dshow_input", "wasapi_output_capture") else 0,
            "muted": False, "volume": 1.0, "sync": 0, "monitoring_type": 0, "private_settings": {}}


def cena(nome, itens):
    return {"id": "scene", "versioned_id": "scene", "name": nome, "uuid": str(uuid.uuid4()),
            "settings": {"id_counter": len(itens), "custom_size": False, "items": itens},
            "enabled": True, "flags": 0, "mixers": 0, "muted": False, "volume": 1.0, "private_settings": {}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta", default=str(RAIZ / "obs"))
    a = ap.parse_args()
    pasta = Path(a.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    cfg = {"titulo": ""}
    for k, n in (("mascote", "caricatura.png"), ("patrocinio", "patrocinio.png")):
        for p in (Path("E:/DETTO/marca"), RAIZ / "marca"):
            if (p / n).exists():
                cfg[k] = str(p / n)
    pos = ["DETTO REAGE — posições das fontes no OBS (pixels da tela base)", ""]
    for fmt in ("horizontal", "vertical"):
        L = R.layout(fmt)
        fundo = R.fundo(cfg, L)
        Image.fromarray(np.ascontiguousarray(fundo[:, :, ::-1])).save(pasta / f"fundo_{fmt}.png")
        moldura_png(L, L["cam"]).save(pasta / f"moldura_camera_{fmt}.png")
        pausa_png(L).save(pasta / f"pausa_{fmt}.png")
        v, c, f = L["video"], L["cam"], L["faixa"]
        pos += [f"{fmt.upper()} ({L['W']}x{L['H']})",
                f"  1. Imagem  fundo_{fmt}.png ............ X 0, Y 0 (tela toda)",
                f"  2. Vídeo reagido (janela do navegador) .. X {v[0]}, Y {v[1]}, caixa {v[2] - v[0]} x {v[3] - v[1]} (Ajustar à caixa)",
                f"  3. Câmera ............................... X {c[0]}, Y {c[1]}, caixa {c[2] - c[0]} x {c[3] - c[1]} (Cobrir e cortar)",
                f"  4. Imagem  moldura_camera_{fmt}.png .... X 0, Y 0 (por cima da câmera)",
                f"  5. Texto do título (fonte Anton, preto) . X {f[0] + 250}, Y {f[1] + 8}, altura {f[3] - f[1] - 16}",
                f"  PAUSA: câmera na tela toda + imagem pausa_{fmt}.png por cima", ""]

    # coleção de cenas (horizontal 1920x1080)
    L = R.layout("horizontal")
    v, c, f = L["video"], L["cam"], L["faixa"]
    # caminho das imagens como o OBS do Everton vê (gerado fora do Windows: a pasta padrão do projeto)
    P = str(pasta).replace("\\", "/") if os.name == "nt" else "C:/Users/guebe/Teste1/obs"
    S = {
        "fundo": fonte_obs("DR Fundo", "image_source", {"file": f"{P}/fundo_horizontal.png"}),
        "video": fonte_obs("DR Vídeo reagido (escolha a janela)", "window_capture", {"method": 2, "cursor": False}),
        "cam": fonte_obs("DR Câmera (escolha a câmera)", "dshow_input", {}),
        "mold": fonte_obs("DR Moldura da câmera", "image_source", {"file": f"{P}/moldura_camera_horizontal.png"}),
        "tit": fonte_obs("DR Título", "text_gdiplus", {"text": "TÍTULO DO REACT", "font": {"face": "Anton", "size": int((f[3] - f[1]) * 0.6), "style": "Regular", "flags": 0},
                                                      "color": 0xFF0A0808, "valign": "center"}),
        "pausa": fonte_obs("DR Selo da pausa", "image_source", {"file": f"{P}/pausa_horizontal.png"}),
    }
    u = {k: s["uuid"] for k, s in S.items()}
    tocando = cena("DETTO REAGE • TOCANDO", [
        item(S["fundo"]["name"], u["fundo"], 1, 0, 0),
        item(S["video"]["name"], u["video"], 2, v[0], v[1], v[2] - v[0], v[3] - v[1]),
        item(S["cam"]["name"], u["cam"], 3, c[0], c[1], c[2] - c[0], c[3] - c[1], cobre=True),
        item(S["mold"]["name"], u["mold"], 4, 0, 0),
        item(S["tit"]["name"], u["tit"], 5, f[0] + 250, f[1] + 6),
    ])
    pausa = cena("DETTO REAGE • PAUSA (EU FALANDO)", [
        item(S["cam"]["name"], u["cam"], 1, 0, 0, L["W"], L["H"], cobre=True),
        item(S["pausa"]["name"], u["pausa"], 2, 0, 0),
    ])
    col = {
        "name": "DETTO REAGE", "current_scene": tocando["name"], "current_program_scene": tocando["name"],
        "scene_order": [{"name": tocando["name"]}, {"name": pausa["name"]}],
        "sources": [*S.values(), tocando, pausa], "groups": [], "quick_transitions": [], "transitions": [],
        "saved_projectors": [], "current_transition": "Fade", "transition_duration": 350,
        "preview_locked": False, "scaling_enabled": False, "scaling_level": 0, "scaling_off_x": 0.0, "scaling_off_y": 0.0,
        "modules": {}, "version": 1,
    }
    (pasta / "DETTO_REAGE_cenas.json").write_text(json.dumps(col, ensure_ascii=False, indent=1), encoding="utf-8")
    (pasta / "POSICOES.txt").write_text("\n".join(pos), encoding="utf-8")
    print(f"Template do OBS em {pasta}")


if __name__ == "__main__":
    main()
