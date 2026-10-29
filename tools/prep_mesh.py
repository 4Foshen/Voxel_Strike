"""Шаг 1: читает исходный GLB солдата, берёт цвета вершин из текстуры, склеивает вершины и упрощает меш."""
import struct,json,io,sys,numpy as np
from PIL import Image
from scipy.spatial import cKDTree
import fast_simplification as fs
SRC=sys.argv[1];OUT=sys.argv[2];TARGET=int(sys.argv[3]) if len(sys.argv)>3 else 20000
d=open(SRC,'rb').read()
l=struct.unpack('<I',d[12:16])[0];bo=20+l+8
j=json.loads(d[20:20+l])
def acc(i):
    a=j['accessors'][i];bv=j['bufferViews'][a['bufferView']]
    o=bo+bv.get('byteOffset',0)+a.get('byteOffset',0)
    dt={5126:'<f4',5125:'<u4',5123:'<u2'}[a['componentType']]
    n={'SCALAR':1,'VEC2':2,'VEC3':3}[a['type']]
    return np.frombuffer(d,dtype=dt,count=a['count']*n,offset=o).reshape(-1,n)
at=j['meshes'][0]['primitives'][0]['attributes']
P=acc(at['POSITION']).astype(np.float64);UV=acc(at['TEXCOORD_0']).astype(np.float64);F=acc(j['meshes'][0]['primitives'][0]['indices']).reshape(-1,3)
bv=j['bufferViews'][j['images'][1]['bufferView']]
img=Image.open(io.BytesIO(d[bo+bv.get('byteOffset',0):bo+bv.get('byteOffset',0)+bv['byteLength']])).convert('RGB')
img.thumbnail((1024,1024));T=np.asarray(img,dtype=np.float32)/255.
H,Wd=T.shape[:2]
u=np.clip(UV[:,0]%1.0,0,1)*(Wd-1);v=np.clip(UV[:,1]%1.0,0,1)*(H-1)   # glTF: v вниз от верха текстуры
C=T[np.round(v).astype(int),np.round(u).astype(int)]
# в мировые оси: поворот узла X+90°: (x,y,z)->(x,-z,y)
W=np.stack([P[:,0],-P[:,2],P[:,1]],1)
# склейка по позиции
key=np.round(W*1e4).astype(np.int64)
_,idx,inv=np.unique(key,axis=0,return_index=True,return_inverse=True)
inv=inv.ravel()
Wp=W[idx];Cs=np.zeros((len(idx),3));cnt=np.zeros(len(idx))
np.add.at(Cs,inv,C);np.add.at(cnt,inv,1);Cs/=cnt[:,None]
Fp=inv[F]
ok=(Fp[:,0]!=Fp[:,1])&(Fp[:,1]!=Fp[:,2])&(Fp[:,0]!=Fp[:,2]);Fp=Fp[ok]
print('welded',len(Wp),len(Fp))
red=1-TARGET/len(Fp)
pts,fcs=fs.simplify(Wp.astype(np.float32),Fp.astype(np.int32),target_reduction=red,agg=5)
print('simplified',len(pts),len(fcs))
# цвета: среднее по ближайшим исходным вершинам
tree=cKDTree(Wp);dd,ii=tree.query(pts,k=6)
col=Cs[ii].mean(1)
np.savez(OUT,pts=pts,faces=fcs,col=col)
