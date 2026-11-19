from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import math,random
base=Path(__file__).parent/'static'
W,H=1200,630
im=Image.new('RGB',(W,H))
pix=im.load()
for y in range(H):
 for x in range(W):
  dist=((x-W/2)**2/(W*.62)**2+(y-H*.38)**2/(H*.86)**2)
  v=max(0,1-dist)
  pix[x,y]=(int(8+33*v),int(7+24*v),int(7+16*v))
d=ImageDraw.Draw(im,'RGBA')
# spotlight cones and curtains
for x in (80,1120):
 d.polygon([(x,-20),(x+30,-20),(x+350,630),(x-330,630)],fill=(215,166,70,9))
for edge in range(0,150,20):
 d.rectangle((edge,0,edge+12,H),fill=(100,7,20,50-edge//3))
 d.rectangle((W-edge-12,0,W-edge,H),fill=(100,7,20,50-edge//3))
# frames
for off in (33,43):
 d.rectangle((off,off,W-off,H-off),outline=(212,175,55,100 if off==33 else 35),width=2)
random.seed(14)
for i in range(45):
 x=random.randint(130,1070);y=random.randint(70,560)
 rr=random.randint(1,3)
 d.ellipse((x-rr,y-rr,x+rr,y+rr),fill=(234,198,107,random.randint(65,160)))
# icon
cx,cy=600,104
pts=[]
for i in range(8):
 a=-math.pi/2+i*math.pi/4
 rad=23 if i%2==0 else 7
 pts.append((cx+rad*math.cos(a),cy+rad*math.sin(a)))
d.polygon(pts,fill=(239,205,122,255))
serif='/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'
italic='/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'
sans='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
f1=ImageFont.truetype(serif,112)
f2=ImageFont.truetype(serif,146)
f3=ImageFont.truetype(sans,30)
f4=ImageFont.truetype(sans,19)
def ct(y,t,font,fill,spacing=0):
 box=d.textbbox((0,0),t,font=font,spacing=spacing)
 d.text(((W-(box[2]-box[0]))/2,y),t,font=font,fill=fill)
ct(138,'OFFICE',f1,(246,235,208,255))
ct(244,'OSCARS',f2,(236,195,102,255))
ct(425,'2 0 2 6',f3,(229,194,115,255))
ct(501,'ГЛАВНАЯ ПРЕМЬЕРА УХОДЯЩЕГО ГОДА',f4,(244,228,199,255))
ct(545,'26 ДЕКАБРЯ 2026  ✦  МОСКВА',f4,(218,182,105,255))
im.save(base/'og-preview.png',optimize=True)
print('created',base/'og-preview.png')
