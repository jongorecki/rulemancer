from PIL import Image, ImageDraw, ImageFont

GARNET=(124,37,48); TAG_L=(150,86,92); PARCH=(242,239,239)
REDBG=(124,37,48); CREAM=(242,239,239); TAG_R=(240,221,217)
SS=3
CIT="D:/Card_Sorter/Scripts/static/branding/fonts/CitadelOfBlackrose.ttf"
ARI="C:/Windows/Fonts/arialbd.ttf"

def lockup(out, bg, wordcol, tagcol, divalpha):
    W,H=1500,470
    img=Image.new("RGB",(W*SS,H*SS),bg); d=ImageDraw.Draw(img,"RGBA")
    icon=Image.open("tome_t.png").convert("RGBA")
    ih=int(360*SS); iw=int(icon.width*ih/icon.height)
    icon=icon.resize((iw,ih),Image.LANCZOS)
    ix=int(40*SS); iy=int((H*SS-ih)/2)
    img.paste(icon,(ix,iy),icon)
    citadel=ImageFont.truetype(CIT,int(150*SS))
    word="Rulemancer"; wx=ix+iw+int(30*SS)
    bb=d.textbbox((0,0),word,font=citadel); wy=int(90*SS)-bb[1]
    d.text((wx,wy),word,font=citadel,fill=wordcol)
    wm_right=wx+(bb[2]-bb[0])
    dy=int(300*SS)
    d.line([(wx+int(4*SS),dy),(wm_right-int(4*SS),dy)],fill=wordcol+(divalpha,),width=int(1.2*SS))
    arial=ImageFont.truetype(ARI,int(23*SS))
    tag="ASK MORE  ·  LEARN MORE  ·  KNOW MORE  ·  WIN MORE"; sp=int(2.5*SS)
    tx=wx+int(6*SS); ty=int(322*SS)
    for ch in tag:
        d.text((tx,ty),ch,font=arial,fill=tagcol); tx+=d.textlength(ch,font=arial)+sp
    img=img.resize((W,H),Image.LANCZOS); img.save(out); print("saved",out,img.size)

def square(out, bg, size=512, pad_frac=0.14):
    icon=Image.open("tome_t.png").convert("RGBA")
    canvas=Image.new("RGB",(size,size),bg)
    inner=int(size*(1-2*pad_frac))
    ih=inner; iw=int(icon.width*ih/icon.height)
    if iw>inner: iw=inner; ih=int(icon.height*iw/icon.width)
    icon=icon.resize((iw,ih),Image.LANCZOS)
    canvas.paste(icon,((size-iw)//2,(size-ih)//2),icon)
    canvas.save(out); print("saved",out,canvas.size)

lockup("rm_lockup_light.png", PARCH, GARNET, TAG_L, 110)
lockup("rm_lockup_red.png",   REDBG, CREAM,  TAG_R, 130)
square("rm_icon_light.png", PARCH)
square("rm_icon_red.png",   REDBG)
