import cairosvg
from PIL import Image

GARNET="#7C2530"; CREAM="#F2EFEF"; AMBER="#3AAE9C"

def rrect_path(x,y,w,h,rtl,rtr,rbr,rbl,fill,stroke="none",sw=0):
    d=(f"M{x+rtl} {y} H{x+w-rtr} Q{x+w} {y} {x+w} {y+rtr} V{y+h-rbr} Q{x+w} {y+h} {x+w-rbr} {y+h} "
       f"H{x+rbl} Q{x} {y+h} {x} {y+h-rbl} V{y+rtl} Q{x} {y} {x+rtl} {y} Z")
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>'

def mark():
    s=[]
    # solid tome cover (bold, no depth layer for small sizes)
    s.append(rrect_path(38,32,108,156, 4,9,9,4, GARNET))
    # spine bar
    s.append(f'<line x1="56" y1="40" x2="56" y2="180" stroke="{CREAM}" stroke-width="3.4" stroke-linecap="round"/>')
    cx=101
    # simplified sigil in cream
    s.append(f'<line x1="{cx}" y1="66" x2="{cx}" y2="150" stroke="{CREAM}" stroke-width="3.6" stroke-linecap="round"/>')
    s.append(f'<path d="M{cx} 68 Q82 78 78 100" fill="none" stroke="{CREAM}" stroke-width="3.4" stroke-linecap="round"/>')
    s.append(f'<path d="M{cx} 68 Q120 78 124 100" fill="none" stroke="{CREAM}" stroke-width="3.4" stroke-linecap="round"/>')
    s.append(f'<path d="M{cx} 103 L{cx+11} 116 L{cx} 129 L{cx-11} 116 Z" fill="none" stroke="{CREAM}" stroke-width="3.2"/>')
    s.append(f'<line x1="{cx}" y1="150" x2="{cx-6}" y2="140" stroke="{CREAM}" stroke-width="3.4" stroke-linecap="round"/>')
    s.append(f'<line x1="{cx}" y1="150" x2="{cx+6}" y2="140" stroke="{CREAM}" stroke-width="3.4" stroke-linecap="round"/>')
    for x,y in [(78,100),(124,100)]:
        s.append(f'<circle cx="{x}" cy="{y}" r="5.2" fill="{CREAM}"/>')
    # amber root
    s.append(f'<circle cx="{cx}" cy="56" r="8.5" fill="{AMBER}"/>')
    return "".join(s)

def svg(bg=None):
    rect=f'<rect x="-24" y="-16" width="256" height="256" fill="{bg}"/>' if bg else ''
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-24 -16 256 256" width="256" height="256">'
            f'{rect}<g transform="rotate(-8 98 114)">{mark()}</g></svg>')

open("rulemancer-favicon.svg","w").write(svg())
cairosvg.svg2png(bytestring=svg().encode(),write_to="fav_hi.png",output_width=512,output_height=512)
img=Image.open("fav_hi.png").convert("RGBA")
for s in (512,180,32,16):
    img.resize((s,s),Image.LANCZOS).save(f"favicon-{s}.png")
# zoom check on white + parchment
for bgc,tag in [((255,255,255,255),"white"),((244,239,228,255),"parch")]:
    c=Image.new("RGBA",(32,32),bgc); c.alpha_composite(img.resize((32,32),Image.LANCZOS))
    c.resize((256,256),Image.NEAREST).convert("RGB").save(f"favcheck_{tag}.png")
print("done")
