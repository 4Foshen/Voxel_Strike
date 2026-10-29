"""Иконки приложения (PWA): воксельный блок травы на тёмном фоне. Запуск: python make_icons.py (рисует в ../icons)"""
import os
from PIL import Image,ImageDraw

def cube(S=64,pad=0):
    """Изометрический блок: рисуем в маленьком разрешении и растягиваем без сглаживания"""
    im=Image.new('RGBA',(S,S),(0,0,0,0));d=ImageDraw.Draw(im)
    cx=S/2;top=S*.16+pad;h=S*.34;w=S*.40
    P=lambda x,y:(cx+x,top+y)
    topf=[P(0,0),P(w,h*.5),P(0,h),P(-w,h*.5)]
    left=[P(-w,h*.5),P(0,h),P(0,h*2.0),P(-w,h*1.5)]
    right=[P(w,h*.5),P(0,h),P(0,h*2.0),P(w,h*1.5)]
    d.polygon(left,fill=(106,74,46,255));d.polygon(right,fill=(86,58,34,255));d.polygon(topf,fill=(96,170,62,255))
    # зелёная «шапка» травы на боках
    d.polygon([P(-w,h*.5),P(0,h),P(0,h*1.22),P(-w,h*.72)],fill=(76,140,48,255))
    d.polygon([P(w,h*.5),P(0,h),P(0,h*1.22),P(w,h*.72)],fill=(62,118,40,255))
    # пиксельные точки-текстура
    import random;r=random.Random(7)
    for poly,cols in((topf,[(120,196,80,255),(78,146,50,255)]),(left,[(124,88,56,255),(90,62,38,255)]),(right,[(102,70,42,255),(70,48,28,255)])):
        xs=[p[0] for p in poly];ys=[p[1] for p in poly]
        for _ in range(26):
            x=r.uniform(min(xs),max(xs));y=r.uniform(min(ys),max(ys))
            if Image.new('1',(1,1)) is None:pass
            d.point((int(x),int(y)),fill=r.choice(cols))
    return im

def icon(size,maskable=False):
    base=64
    bg=Image.new('RGBA',(base,base),(16,20,24,255));d=ImageDraw.Draw(bg)
    for y in range(base):                                   # небо -> тёмный низ
        t=y/base;d.line([(0,y),(base,y)],fill=(int(30+30*(1-t)),int(60+70*(1-t)),int(110+90*(1-t)),255) if t<.62 else (24,30,38,255))
    c=cube(base)
    if maskable:                                            # безопасная зона маскируемой иконки - центральные ~60%
        c=c.resize((int(base*.62),int(base*.62)),Image.NEAREST);bg.alpha_composite(c,((base-c.width)//2,(base-c.height)//2-1))
    else:
        bg.alpha_composite(c,(0,2))
    # красный прицел-акцент
    a=ImageDraw.Draw(bg);k=int(base*(.86 if not maskable else .74));m=int(base*.1)
    for dx,dy in((0,-1),(0,1),(-1,0),(1,0)):
        for i in range(3,6):a.point((k+dx*i,m+dy*i),fill=(255,80,70,255))
    return bg.resize((size,size),Image.NEAREST).convert('RGB')

os.makedirs('../icons',exist_ok=True)
for name,size,mk in(('icon-192.png',192,False),('icon-512.png',512,False),('icon-maskable-512.png',512,True),('apple-touch-icon.png',180,False)):
    icon(size,mk).save('../icons/'+name);print(name,size)
