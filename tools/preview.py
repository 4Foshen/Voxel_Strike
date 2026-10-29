import sys,numpy as np
from PIL import Image,ImageDraw
def render(pts,faces,col,out,view='front',S=700,pose=None):
    # view: front = смотрим с +z на модель (камера на +z), back = с -z, side
    p=pts.copy()
    if view=='back':p[:,0]*=-1;p[:,2]*=-1
    if view=='side':p=np.stack([-p[:,2],p[:,1],p[:,0]],1)
    x=p[:,0];y=p[:,1];z=p[:,2]
    sc=S/ (pts[:,1].max()*1.05)
    cx=sc*x+S*0.5;cy=S-(sc*y+10)
    tri=faces;zc=z[tri].mean(1);order=np.argsort(zc)
    im=Image.new('RGB',(S,S),(30,30,34));dr=ImageDraw.Draw(im)
    fc=col[tri].mean(1)
    for t in order:
        a,b,c=tri[t]
        dr.polygon([(cx[a],cy[a]),(cx[b],cy[b]),(cx[c],cy[c])],fill=tuple((np.clip(fc[t],0,1)*255).astype(int)))
    im.save(out)
if __name__=='__main__':
    d=np.load(sys.argv[1]);
    for v in ('front','back','side'):render(d['pts'],d['faces'],d['col'],f'{sys.argv[2]}_{v}.png',v)
