import cairosvg
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
import tome  # provides tome.tome() and color constants; running it also (re)renders the icon

CIT="D:/Card_Sorter/Scripts/static/branding/fonts/CitadelOfBlackrose.ttf"
ARI="C:/Windows/Fonts/arialbd.ttf"

def text_paths(fontpath, text, size, x, baseline, color, spacing=0.0):
    f=TTFont(fontpath); upm=f['head'].unitsPerEm; cmap=f.getBestCmap()
    gs=f.getGlyphSet(); hmtx=f['hmtx']; s=size/upm; penx=x; out=[]
    for ch in text:
        gname=cmap.get(ord(ch))
        if gname is None:
            penx+=size*0.3+spacing; continue
        pen=SVGPathPen(gs); gs[gname].draw(pen); d=pen.getCommands()
        adv=hmtx[gname][0]
        if d.strip():
            out.append(f'<path d="{d}" fill="{color}" '
                       f'transform="translate({penx:.2f} {baseline:.2f}) scale({s:.5f} {-s:.5f})"/>')
        penx+=adv*s+spacing
    return "".join(out), penx

def icon_group():
    # place tome (its own coord box viewBox -20 -16 248 256) at x=40, 360px tall
    s=360/256; tx=40+20*s; ty=55+16*s
    return (f'<g transform="translate({tx:.3f} {ty:.3f}) scale({s:.5f})" '
            f'stroke-linejoin="round" stroke-linecap="round">'
            f'<g transform="rotate(-8 98 114)">{tome.tome()}</g></g>')

def lockup_svg(bg, wordcol, tagcol, divcol, divop):
    wx=418.75
    word,wr=text_paths(CIT,"Rulemancer",150,wx,262,wordcol)
    div=f'<line x1="{wx+4:.1f}" y1="292" x2="{wr-4:.1f}" y2="292" stroke="{divcol}" stroke-opacity="{divop}" stroke-width="1.4"/>'
    tag,_=text_paths(ARI,"ASK MORE  ·  LEARN MORE  ·  KNOW MORE  ·  WIN MORE",23,wx+6,332,tagcol,spacing=2.5)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1500 470" width="1500" height="470">'
            f'<rect width="1500" height="470" fill="{bg}"/>'
            f'{icon_group()}{word}{div}{tag}</svg>')

light=lockup_svg("#F2EFEF","#7C2530","#96565C","#7C2530",0.43)
red  =lockup_svg("#7C2530","#F2EFEF","#F0DDD9","#F2EFEF",0.5)
open("rulemancer-lockup-light.svg","w").write(light)
open("rulemancer-lockup-red.svg","w").write(red)
cairosvg.svg2png(bytestring=light.encode(),write_to="check_light.png",output_width=1500)
cairosvg.svg2png(bytestring=red.encode(),write_to="check_red.png",output_width=1500)
print("built lockup SVGs; wordmark right edge computed")
