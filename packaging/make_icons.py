"""Genera le icone dell'app (PNG, ICO per Windows, ICNS per macOS).

Uso: python packaging/make_icons.py   (richiede Pillow)
Le icone generate sono gia' incluse nel repository: rieseguilo solo se
vuoi cambiarne il disegno.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).parent / "icons"
S = 1024


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # Sfondo: quadrato arrotondato con sfumatura verticale.
    bg = Image.new("RGBA", (S, S))
    top, bottom = (36, 42, 74, 255), (12, 14, 28, 255)
    px = bg.load()
    for y in range(S):
        c = lerp(top, bottom, y / (S - 1))
        for x in range(S):
            px[x, y] = c
    mask = Image.new("L", (S, S), 0)
    m = 64
    ImageDraw.Draw(mask).rounded_rectangle((m, m, S - m, S - m), radius=200, fill=255)
    img.paste(bg, (0, 0), mask)

    # Cubo isometrico: le tre facce in colori "RGB" richiamano la grafica 3D.
    cx, cy, r = S // 2, S // 2 + 30, 270
    import math
    pts = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
           for a in (-90, -30, 30, 90, 150, 210)]
    center = (cx, cy)
    faces = [
        ([pts[5], pts[0], pts[1], center], (255, 196, 64, 255)),   # sopra
        ([pts[4], pts[5], center, pts[3]], (40, 200, 190, 255)),    # sinistra
        ([center, pts[1], pts[2], pts[3]], (226, 64, 140, 255)),    # destra
    ]

    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for poly, col in faces:
        gd.polygon(poly, fill=col[:3] + (150,))
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    img.alpha_composite(glow)

    d = ImageDraw.Draw(img)
    for poly, col in faces:
        d.polygon(poly, fill=col)
    # Spigoli chiari per dare profondita'.
    edge = (255, 255, 255, 200)
    for a, b in ((center, pts[5]), (center, pts[1]), (center, pts[3])):
        d.line([a, b], fill=edge, width=10)
    d.line(pts + [pts[0]], fill=(255, 255, 255, 120), width=8, joint="curve")
    return img


def main() -> None:
    OUT.mkdir(exist_ok=True)
    img = draw()
    img.resize((512, 512), Image.LANCZOS).save(OUT / "app.png")
    img.save(OUT / "app.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                     (64, 64), (128, 128), (256, 256)])
    img.save(OUT / "app.icns")
    print("Icone scritte in", OUT)


if __name__ == "__main__":
    main()
