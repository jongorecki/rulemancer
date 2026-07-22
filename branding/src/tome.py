import cairosvg

RED="#7C2530"; REDL="#B0666C"
ROSE_PAGE="#EAD8DB"; ROSE_DEEP="#D9BEC2"; AMBER="#309B8C"; PARCH="#F2EFEF"

def rrect(x,y,w,h,r,fill,stroke,sw):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" ry="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
def rrect_path(x,y,w,h,rtl,rtr,rbr,rbl,fill,stroke,sw):
    d=(f"M{x+rtl} {y} H{x+w-rtr} Q{x+w} {y} {x+w} {y+rtr} "
       f"V{y+h-rbr} Q{x+w} {y+h} {x+w-rbr} {y+h} "
       f"H{x+rbl} Q{x} {y+h} {x} {y+h-rbl} "
       f"V{y+rtl} Q{x} {y} {x+rtl} {y} Z")
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>'
def dot(x,y,r=2.1,c=RED): return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}"/>'
def line(x1,y1,x2,y2,sw=2.2,c=RED): return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="{sw}" stroke-linecap="round"/>'

def ring(x,y,r,fill=ROSE_PAGE,sw=2.1):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{RED}" stroke-width="{sw}"/>'

def glyph():
    """Arcane branching sigil — a mystical glyph with a top-down tree hint."""
    cx=100
    s=[]
    # central staff
    s.append(line(cx,60,cx,150,2.1))
    # upper branches: curved, root -> side rings
    s.append(f'<path d="M{cx} 63 Q80 72 74 94" fill="none" stroke="{RED}" stroke-width="2.1" stroke-linecap="round"/>')
    s.append(f'<path d="M{cx} 63 Q120 72 126 94" fill="none" stroke="{RED}" stroke-width="2.1" stroke-linecap="round"/>')
    # lower branches: curved, side rings -> terminals
    s.append(f'<path d="M74 102 Q72 128 80 148" fill="none" stroke="{RED}" stroke-width="2.1" stroke-linecap="round"/>')
    s.append(f'<path d="M126 102 Q128 128 120 148" fill="none" stroke="{RED}" stroke-width="2.1" stroke-linecap="round"/>')
    # central diamond (arcane eye) — staff passes through
    my=112
    s.append(f'<path d="M{cx} {my-11} L{cx+10} {my} L{cx} {my+11} L{cx-10} {my} Z" fill="none" stroke="{RED}" stroke-width="2.1"/>')
    # bottom downward arrowhead (sigil echo)
    s.append(line(cx,150,cx-5,141,2.1)); s.append(line(cx,150,cx+5,141,2.1))
    # side ring nodes
    s.append(ring(74,94,5)); s.append(ring(126,94,5))
    # terminal nodes — accent-filled (root + bottom outside nodes carry the accent)
    for x,y in [(80,148),(120,148)]:
        s.append(f'<circle cx="{x}" cy="{y}" r="4.3" fill="{AMBER}" stroke="{RED}" stroke-width="1.9"/>')
    # root: accent node (ritual accent)
    s.append(f'<circle cx="{cx}" cy="55" r="6.5" fill="{AMBER}" stroke="{RED}" stroke-width="2.2"/>')
    return "".join(s)

def tome():
    s=[]
    # depth layer (pages / back cover), offset down-right — echoes Cardomancer's 2nd card
    # spine side (left) squared, fore-edge (right) softly rounded
    s.append(rrect_path(52,44,104,150, 3,7,7,3, ROSE_DEEP,RED,2.2))
    # front cover
    s.append(rrect_path(40,34,104,150, 3,7,7,3, ROSE_PAGE,RED,2.5))
    # spine: vertical line near left + two binding bands
    sx=56
    s.append(line(sx,44,sx,174,2.2))
    s.append(line(40,60,sx,60,2.0)); s.append(line(40,158,sx,158,2.0))
    # corner dots on the front cover (fore-edge side only; spine side stays clean)
    for (dx,dy) in [(132,46),(132,172)]:
        s.append(dot(dx,dy,2.1))
    # arcane branching sigil on the cover face (right of spine)
    s.append(glyph())
    return "".join(s)

def svg(bg=True):
    # rotate the whole tome CCW ~8 deg to match Cardomancer's card angle
    rect=f'<rect x="-20" y="-16" width="248" height="256" fill="{PARCH}"/>' if bg else ''
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-20 -16 248 256" width="248" height="256">'
            f'<g stroke-linejoin="round" stroke-linecap="round">{rect}'
            f'<g transform="rotate(-8 98 114)">{tome()}</g></g></svg>')

open("tome.svg","w").write(svg(False))
cairosvg.svg2png(bytestring=svg(True).encode(),write_to="tome.png",output_width=744,output_height=768)
cairosvg.svg2png(bytestring=svg(False).encode(),write_to="tome_t.png",output_width=992,output_height=1024)
print("saved")
