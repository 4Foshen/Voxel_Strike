"""Шаг 3: пишет riggeд GLB с скелетом, весами и клипами."""
import json,struct,base64,os,numpy as np
import rig
from rig import *
OUT='../assets/models'
os.makedirs(OUT,exist_ok=True)
bin_=bytearray();views=[];accs=[]
def pad():
    while len(bin_)%4:bin_.append(0)
def put(arr,ctype,typ,target=None,minmax=False,norm=False):
    pad();off=len(bin_);b=arr.tobytes();bin_.extend(b)
    views.append({'buffer':0,'byteOffset':off,'byteLength':len(b),**({'target':target} if target else {})})
    cnt=arr.shape[0];a={'bufferView':len(views)-1,'componentType':ctype,'count':cnt,'type':typ}
    if norm:a['normalized']=True
    if minmax:a['min']=arr.min(0).tolist();a['max']=arr.max(0).tolist()
    accs.append(a);return len(accs)-1
N=len(NAMES)
pts=(PTS*S).astype(np.float32)
a_pos=put(pts,5126,'VEC3',34962,True)
rgba=np.concatenate([np.clip(COL*255,0,255).astype(np.uint8),np.full((len(COL),1),255,np.uint8)],1)
a_col=put(rgba,5121,'VEC4',34962,norm=True)
a_j=put(top.astype(np.uint8),5121,'VEC4',34962)
a_w=put(W4.astype(np.float32),5126,'VEC4',34962)
a_i=put(FAC.astype(np.uint16).reshape(-1),5123,'SCALAR',34963)
ibm=np.zeros((N,16),np.float32)
for i,n in enumerate(NAMES):
    m=np.eye(4);m[:3,3]=-P0[n]*S;ibm[i]=m.T.reshape(-1)    # column-major
a_ibm=put(ibm,5126,'MAT4')
# узлы: 0 корень, 1 тело, 2.. кости
BONE0=2
nodes=[{'name':'Soldier','children':[1,BONE0+IDX['Hips']]},{'name':'Body','mesh':0,'skin':0}]
for n in NAMES:
    p=PAR[n];t=(P0[n]-(P0[p] if p else 0))*S
    nd={'name':n.replace('.','_'),'translation':[float(x) for x in t]}
    ch=[BONE0+IDX[c] for c in NAMES if PAR[c]==n]
    if ch:nd['children']=ch
    nodes.append(nd)
# метаданные хвата оружия
gun={}
for sd in 'LR':
    Mr=hand_rest_frame(sd);f0=Mr[:,2]
    gun[sd]={'m':[float(x) for x in Mr.T.reshape(-1)],'p':[float(x) for x in f0*GRIP_OFF*S]}  # колонки x,y,z
nodes[0]['extras']={'gun':gun,'clips':list(CLIPS.keys())}
anims=[]
for name,(T,frames,nf) in CLIPS.items():
    times=np.array([i/nf*T for i in range(len(frames))],np.float32)
    a_t=put(times.reshape(-1,1),5126,'SCALAR',minmax=True)
    samplers=[];channels=[]
    for n in NAMES:
        q=np.array([f[0][n].as_quat() for f in frames],np.float32)
        for i in range(1,len(q)):
            if q[i]@q[i-1]<0:q[i]=-q[i]
        if np.abs(q-q[0]).max()<1e-6 and n not in('Hips','Spine','Chest','Head','Neck'):continue
        samplers.append({'input':a_t,'output':put(q,5126,'VEC4'),'interpolation':'LINEAR'})
        channels.append({'sampler':len(samplers)-1,'target':{'node':BONE0+IDX[n],'path':'rotation'}})
    tr=np.array([(P0['Hips']+f[1])*S for f in frames],np.float32)
    samplers.append({'input':a_t,'output':put(tr,5126,'VEC3'),'interpolation':'LINEAR'})
    channels.append({'sampler':len(samplers)-1,'target':{'node':BONE0+IDX['Hips'],'path':'translation'}})
    anims.append({'name':name,'samplers':samplers,'channels':channels})
g={'asset':{'version':'2.0','generator':'voxel-strike rig.py'},'scene':0,'scenes':[{'nodes':[0]}],'nodes':nodes,
 'meshes':[{'name':'Body','primitives':[{'attributes':{'POSITION':a_pos,'COLOR_0':a_col,'JOINTS_0':a_j,'WEIGHTS_0':a_w},'indices':a_i,'material':0}]}],
 'skins':[{'joints':[BONE0+i for i in range(N)],'inverseBindMatrices':a_ibm,'skeleton':BONE0+IDX['Hips']}],
 'materials':[{'name':'Soldier','pbrMetallicRoughness':{'baseColorFactor':[1,1,1,1],'metallicFactor':0,'roughnessFactor':1},'extensions':{'KHR_materials_unlit':{}}}],
 'extensionsUsed':['KHR_materials_unlit'],
 'animations':anims,'accessors':accs,'bufferViews':views,'buffers':[{'byteLength':len(bin_)}]}
js=json.dumps(g,separators=(',',':')).encode()
while len(js)%4:js+=b' '
pad()
glb=struct.pack('<III',0x46546C67,2,12+8+len(js)+8+len(bin_))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bin_),0x004E4942)+bytes(bin_)
open(OUT+'/soldier.glb','wb').write(glb)
open(OUT+'/soldier_glb.js','w').write('window.SOLDIER_GLB_B64="'+base64.b64encode(glb).decode()+'";\n')
print('GLB',len(glb),'bytes; bones',N,'clips',list(CLIPS.keys()));print(json.dumps(gun))
