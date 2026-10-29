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
def arms(loc,htr,pose,gs=(0,0,0)):
    Rw,Pw=fk(loc,htr)
    Rc=Rw['Chest'];Pc=Pw['Chest']
    G,F=GUN[pose];G=np.array(G)+np.array(gs);F=unit(F)
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

def locomotion(t,T,A,K,bob,lean,pose,mode='fwd',side=1):
    """mode: idle - перенос веса и осмотр; fwd - шаг/бег; strafe - боковой шаг (side=+1 влево персонажа, -1 вправо)"""
    loc={n:R.identity() for n in NAMES}
    aimk=.5 if pose=='aim' else 1.0
    htr=np.zeros(3);gs=np.zeros(3)
    if mode=='idle':
        w=2*np.pi*t/3.0;sh=np.sin(w);b=np.sin(w*2+.3)
        htr=np.array([.012*sh,-.004*abs(sh)+.003*b,0])
        loc['Hips']=RZ(.028*sh)*RY(.035*np.sin(w+1))
        for sd,sg in(('L',1),('R',-1)):       # на ногу, на которую смещён вес, - прямая; другая слегка согнута
            un=max(0.,-sh*sg)
            loc['UpLeg.'+sd]=RX(-.06*un)*RZ(-.012*sh*sg);loc['LowLeg.'+sd]=RX(.14*un);loc['Foot.'+sd]=RX(-.08*un)
        loc['Foot.R']=loc['Foot.R']*RX(.1*max(0.,np.sin(w*2)))      # лёгкий перетоп носком
        loc['Spine']=RX(.006*b)*RZ(-.012*sh);loc['Chest']=RX(.015*b)*RZ(-.014*sh)*RY(.02*np.sin(w+2))
        yaw=(.24*np.sin(w)+.1*np.sin(2*w+1))*aimk;pit=.05*np.sin(3*w)*aimk
        loc['Neck']=RY(yaw*.4)*RX(pit*.4);loc['Head']=RY(yaw*.6)*RX(pit*.6)
        gs=np.array([.006*np.sin(2*w),.006*b,0])
    elif mode=='strafe':
        ph=2*np.pi*t/T;D=.3
        for sd,sg in(('L',1),('R',-1)):
            pi_=ph+(0 if sg>0 else np.pi);sn=np.sin(pi_);cs=np.cos(pi_)
            # ведущая нога уходит в сторону, вторая подтягивается; колено сгибается при переносе
            loc['UpLeg.'+sd]=RZ(side*D*(.5+.5*sn))*RX(-.12*cs)
            kn=.55*max(0.,cs);loc['LowLeg.'+sd]=RX(kn);loc['Foot.'+sd]=RZ(-side*D*(.5+.5*sn))*RX(-kn*.5)
        s_=np.sin(ph)
        htr=np.array([side*.03*s_,-.03-.02*np.cos(2*ph),0])
        loc['Hips']=RZ(-side*.05*s_)*RY(.05*np.sin(ph));loc['Spine']=RZ(side*.03*s_)*RX(.05);loc['Chest']=RY(-.06*np.sin(ph))*RX(.06)
        loc['Head']=RX(-.05)
        gs=np.array([.01*np.sin(ph),.012*np.cos(2*ph),0])
    else:
        ph=2*np.pi*t/T;s=np.sin(ph);c=np.cos(ph);k=A/.45
        for sd,sg in(('L',1),('R',-1)):
            th=-A*s*sg;kn=K*max(0.,c*sg)+.08*K
            loc['UpLeg.'+sd]=RX(th);loc['LowLeg.'+sd]=RX(kn)
            loc['Foot.'+sd]=RX(.4*th/A-(th+kn))            # пятка-носок: носок вверх при выносе, вниз при отталкивании
        htr=np.array([.022*k*np.sin(ph),-bob*(.6-.4*np.cos(2*ph)),0])
        loc['Hips']=RY(.12*k*s)*RZ(.045*k*s)
        loc['Spine']=RX(lean*.5)*RY(-.07*k*s)*RZ(-.03*k*s)
        loc['Chest']=RX(lean*.5)*RY(-.10*k*s)*RZ(-.02*k*s)
        loc['Neck']=RY(.03*k*s)
        loc['Head']=RY(.02*k*s)*RX(-lean*.7+.025*k*np.cos(2*ph))     # голова стабилизируется против качки корпуса
        gs=np.array([.012*k*np.sin(ph+.3),.014*k*np.cos(2*ph),.008*k*np.sin(2*ph)])
    return arms(loc,htr,pose,gs),htr

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
mk('idle',3.0,lambda t:locomotion(t,0,0,0,0,0,'ready','idle'),45)
mk('aim_idle',3.0,lambda t:locomotion(t,0,0,0,0,0,'aim','idle'),45)
mk('walk',1.0,lambda t:locomotion(t,1.0,.45,.75,.02,.05,'ready'),30)
mk('aim_walk',1.0,lambda t:locomotion(t,1.0,.45,.75,.02,.05,'aim'),30)
mk('run',.64,lambda t:locomotion(t,.64,.85,1.05,.045,.24,'ready'),24)
mk('aim_run',.64,lambda t:locomotion(t,.64,.85,1.05,.045,.24,'aim'),24)
mk('strafe_l',.8,lambda t:locomotion(t,.8,0,0,0,0,'aim','strafe',1),24)
mk('strafe_r',.8,lambda t:locomotion(t,.8,0,0,0,0,'aim','strafe',-1),24)
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
