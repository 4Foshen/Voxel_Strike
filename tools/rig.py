"""Шаг 2: скелет, веса, запечённые анимации. Импортируется из build_glb.py; запуск напрямую рисует предпросмотр поз."""
import sys,numpy as np
from scipy.spatial.transform import Rotation as R

d=np.load('soldier_lo.npz');PTS=d['pts'].astype(np.float64);FAC=d['faces'];COL=d['col']
PTS[:,1]-=PTS[:,1].min()
H=PTS[:,1].max();S=1.8/H            # итоговая высота 1.8 (как хитбокс)

# ---------- скелет (в исходном масштабе модели) ----------
J={}
def add(n,p,par):J[n]=(np.array(p,float),par)
add('Hips',(0,.50,0),None);add('Spine',(0,.56,0),'Hips');add('Chest',(0,.68,0),'Spine');add('Neck',(0,.86,0),'Chest');add('Head',(0,.92,0),'Neck')
for sd,sg in(('L',1),('R',-1)):
    add('UpperArm.'+sd,(.134*sg,.78,0),'Chest');add('LowerArm.'+sd,(.252*sg,.613,0),'UpperArm.'+sd);add('Hand.'+sd,(.35*sg,.48,0),'LowerArm.'+sd)
    add('UpLeg.'+sd,(.07*sg,.50,0),'Hips');add('LowLeg.'+sd,(.07*sg,.27,0),'UpLeg.'+sd);add('Foot.'+sd,(.07*sg,.06,0),'LowLeg.'+sd)
NAMES=list(J.keys());IDX={n:i for i,n in enumerate(NAMES)}
P0={n:J[n][0] for n in NAMES};PAR={n:J[n][1] for n in NAMES}
TIP={'Head':np.array((0,1.12,0)),'Hand.L':np.array((.385,.41,0)),'Hand.R':np.array((-.385,.41,0)),'Foot.L':np.array((.07,0,.13)),'Foot.R':np.array((-.07,0,.13))}

# ---------- веса: расстояние до отрезков кости (у корпуса X сжат, чтобы бока не липли к рукам) ----------
def seg_dist(P,a,b,xs=1.0):
    ab=b-a;t=np.clip(((P-a)@ab)/(ab@ab),0,1);c=a+t[:,None]*ab;dd=P-c;dd[:,0]*=xs;return np.linalg.norm(dd,axis=1)
segs={}
for n in NAMES:
    ch=[c for c in NAMES if PAR[c]==n];a=P0[n]
    if n in TIP:b=TIP[n]
    elif n=='Hips':b=P0['Spine']
    elif n=='Neck':b=P0['Head']
    else:b=P0[ch[0]]
    xs={'Hips':.4,'Spine':.35,'Chest':.35,'Neck':.5,'Head':.6}.get(n,1.0)
    segs[n]=(a,b,xs)
D=np.stack([seg_dist(PTS,*segs[n]) for n in NAMES],1)
Wt=1.0/(D+.012)**6
top=np.argsort(-Wt,1)[:,:4];W4=np.take_along_axis(Wt,top,1);W4/=W4.sum(1,keepdims=True)
W4[W4<.03]=0;W4/=W4.sum(1,keepdims=True)

# ---------- FK ----------
OFF={n:P0[n]-(P0[PAR[n]] if PAR[n] else 0*P0[n]) for n in NAMES}
def fk(loc,htr):
    Rw={};Pw={}
    for n in NAMES:
        p=PAR[n]
        if p is None:Rw[n]=loc[n];Pw[n]=P0[n]+htr
        else:Rw[n]=Rw[p]*loc[n];Pw[n]=Pw[p]+Rw[p].apply(OFF[n])
    return Rw,Pw
def rb(a,b):
    a=a/np.linalg.norm(a);b=b/np.linalg.norm(b);c=np.cross(a,b);s=np.linalg.norm(c);dt=a@b
    if s<1e-9:
        if dt>0:return R.identity()
        ax=np.cross(a,[1,0,0])
        if np.linalg.norm(ax)<1e-6:ax=np.cross(a,[0,1,0])
        return R.from_rotvec(ax/np.linalg.norm(ax)*np.pi)
    return R.from_rotvec(c/s*np.arctan2(s,dt))
RX=lambda a:R.from_rotvec([a,0,0]);RY=lambda a:R.from_rotvec([0,a,0]);RZ=lambda a:R.from_rotvec([0,0,a])
def unit(v):v=np.array(v,float);return v/np.linalg.norm(v)

L1={};L2={}
for sd in 'LR':
    L1[sd]=np.linalg.norm(P0['LowerArm.'+sd]-P0['UpperArm.'+sd]);L2[sd]=np.linalg.norm(P0['Hand.'+sd]-P0['LowerArm.'+sd])
# хват: позиция и направление ствола в системе груди
GUN={'ready':((-.08,-.03,.30),(.06,-.40,1.0)),'aim':((-.04,.08,.31),(.02,.0,1.0))}
GRIP_OFF=.06
def hand_rest_frame(sd):
    f0=unit(TIP['Hand.'+sd]-P0['Hand.'+sd]);u0=np.array([0,0,1.]);u0=unit(u0-(u0@f0)*f0);x0=np.cross(u0,f0)
    return np.stack([x0,u0,f0],1)     # колонки: оси gun x,y,z в пространстве кости
def arms(loc,htr,pose):
    Rw,Pw=fk(loc,htr)
    Rc=Rw['Chest'];Pc=Pw['Chest']
    G,F=GUN[pose];G=np.array(G);F=unit(F)
    U=unit(np.array([0,1.,0])-F*F[1]);X=np.cross(U,F)
    Mg=np.stack([X,U,F],1)
    for sd,sg in(('L',1),('R',-1)):
        sh=Pw['UpperArm.'+sd]
        tgt_loc=G if sd=='R' else G+F*.15+np.array([0,-.015,0])
        T=Pc+Rc.apply(tgt_loc)
        v=T-sh;dd=np.linalg.norm(v);l1,l2=L1[sd],L2[sd];dd=min(max(dd,.06),(l1+l2)*.995);u=v/np.linalg.norm(v)
        a=(l1*l1-l2*l2+dd*dd)/(2*dd);h=np.sqrt(max(l1*l1-a*a,1e-6))
        pole=np.array([sg*.6,-1,-.25]);pp=pole-(pole@u)*u;pp/=np.linalg.norm(pp)
        E=sh+u*a+pp*h;Hd=sh+u*dd
        ru=P0['LowerArm.'+sd]-P0['UpperArm.'+sd];rl=P0['Hand.'+sd]-P0['LowerArm.'+sd]
        Wu=rb(ru,E-sh);Wl=rb(rl,Hd-E)
        loc['UpperArm.'+sd]=Rw['Chest'].inv()*Wu
        loc['LowerArm.'+sd]=Wu.inv()*Wl
        Mw=Rc.as_matrix()@Mg;Mr=hand_rest_frame(sd)
        loc['Hand.'+sd]=Wl.inv()*R.from_matrix(Mw@Mr.T)
    return loc

def locomotion(t,T,A,K,bob,lean,pose):
    ph=2*np.pi*t/T if T else 0
    loc={n:R.identity() for n in NAMES}
    s=np.sin(ph);c=np.cos(ph);k=(A/.45) if A else 0
    for sd,sg in(('L',1),('R',-1)):
        th=-A*s*sg
        kn=(K*max(0.,c*sg)+.06*K) if A>0 else 0
        loc['UpLeg.'+sd]=RX(th);loc['LowLeg.'+sd]=RX(kn);loc['Foot.'+sd]=RX(-(th+kn)*.6)
    loc['Spine']=RX(lean*.5)*RY(-.10*s*k)
    loc['Chest']=RX(lean*.5)*RY(.12*s*k)
    loc['Head']=RY(-.08*s*k)*RX(-lean*.6)
    loc['Hips']=RY(.10*s*k)
    if A>0:htr=np.array([0,-abs(s)*bob-bob*.4,0])
    else:
        b=np.sin(2*np.pi*t/3.0);loc['Chest']=RX(.012*b)*loc['Chest'];htr=np.array([0,.004*b,0])
    return arms(loc,htr,pose),htr

def die(t):
    k=min(1,t/1.2);e=k*k*(3-2*k)
    loc={n:R.identity() for n in NAMES}
    loc['Hips']=RX(-1.45*e);loc['Head']=RX(.5*e)
    loc['UpLeg.L']=RX(.5*e)*RZ(-.2*e);loc['UpLeg.R']=RX(.2*e)*RZ(.2*e);loc['LowLeg.L']=RX(.7*e);loc['LowLeg.R']=RX(.2*e)
    loc['UpperArm.L']=RZ(-1.2*e);loc['UpperArm.R']=RZ(1.1*e)
    return loc,np.array([0,-.37*e,-.05*e])

CLIPS={}
def mk(name,T,fn,frames,loop=True):
    CLIPS[name]=(T,[fn(i/frames*T) for i in range(frames+1)],frames)
mk('idle',3.0,lambda t:locomotion(t,0,0,0,0,0,'ready'),30)
mk('aim_idle',3.0,lambda t:locomotion(t,0,0,0,0,0,'aim'),30)
mk('walk',1.0,lambda t:locomotion(t,1.0,.45,.7,.012,.04,'ready'),30)
mk('aim_walk',1.0,lambda t:locomotion(t,1.0,.45,.7,.012,.04,'aim'),30)
mk('run',.64,lambda t:locomotion(t,.64,.85,1.35,.03,.22,'ready'),24)
mk('aim_run',.64,lambda t:locomotion(t,.64,.85,1.35,.03,.22,'aim'),24)
mk('die',1.2,die,24,loop=False)

def skin(loc,htr):
    Rw,Pw=fk(loc,htr);out=np.zeros_like(PTS)
    for k in range(4):
        for bi,n in enumerate(NAMES):
            m=top[:,k]==bi
            if m.any():out[m]+=W4[m,k,None]*(Rw[n].apply(PTS[m]-P0[n])+Pw[n])
    return out

if __name__=='__main__':
    from preview import render
    from PIL import Image
    SC='C:/Users/Danil/AppData/Local/Temp/claude/C--Users-Danil-Desktop-voxel-strike-project/ef17535f-d3d5-42ab-b0a2-38e89675afa2/scratchpad/'
    ims=[]
    for name,fi in(('aim_idle',0),('walk',8),('run',6),('die',20)):
        T,fr,n=CLIPS[name];loc,htr=fr[fi];p=skin(loc,htr)
        for v in('side','front'):
            render(p,FAC,COL,SC+'x.png',v);ims.append(Image.open(SC+'x.png').copy())
    c=Image.new('RGB',(700*4,1400))
    for i,im in enumerate(ims):c.paste(im,((i//2)*700,(i%2)*700))
    c.save(SC+'pose.png')
