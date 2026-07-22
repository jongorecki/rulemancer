import cairosvg
from PIL import Image

# hi-res lockup PNGs rendered from the self-contained SVGs (vector-crisp text)
for name in ("light","red"):
    svg=open(f"rulemancer-lockup-{name}.svg").read()
    cairosvg.svg2png(bytestring=svg.encode(),write_to=f"rulemancer-lockup-{name}.png",output_width=1500)
    cairosvg.svg2png(bytestring=svg.encode(),write_to=f"rulemancer-lockup-{name}@2x.png",output_width=3000)

# square solid-background app icons (detailed mark)  [favicons come from favicon.py]
mark=Image.open("tome_t.png").convert("RGBA")
side=int(max(mark.size)*1.14)
def solid(bg,tag):
    c=Image.new("RGBA",(side,side),bg); c.paste(mark,((side-mark.width)//2,(side-mark.height)//2),mark)
    c.convert("RGB").resize((512,512),Image.LANCZOS).save(f"rulemancer-icon-512-{tag}.png")
solid((242,239,239,255),"light"); solid((124,37,48,255),"red")
print("done")
