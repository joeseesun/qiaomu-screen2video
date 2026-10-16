import cv2,numpy as np,subprocess
FPS=30;OW,OH=2972,1672   # 2x of the 1486x836 plate
SRC="$PROJECT/音频功能介绍.mp4"
c=np.load("cam.npz");Z,CX,CY=c["z"],c["cx"],c["cy"];px,py=c["px"],c["py"]
K=3226/2880   # proxy(2880) -> native crop px
S=OW/3226     # native crop px -> plate px
def p2proxy_old(ox,oy,tt,OWold=1632):   # override coords were read off the old 1632px plate with the old camera
    k=int(tt*FPS);z=Z[k];w=2880/z;x0=CX[k]-w/2;y0=CY[k]-(1620/z)/2;s=OWold/w
    return x0+ox/s,y0+oy/s
clicks=[]
for t in (43.9,86.9,130.7):
    if t==86.9: x,y=p2proxy_old(688,98,87.0)
    else: x,y=float(px[int(t*FPS)]),float(py[int(t*FPS)])
    clicks.append((t,x*K*S,y*K*S))
cap=cv2.VideoCapture(SRC)
ff=subprocess.Popen(["ffmpeg","-y","-v","error","-f","rawvideo","-pix_fmt","bgr24","-s",f"{OW}x{OH}","-r","30","-i","-","-c:v","libx264","-preset","veryfast","-crf","10","-pix_fmt","yuv420p","plate4k.mp4"],stdin=subprocess.PIPE)
i=0;n=0
while True:
    ok=cap.grab()
    if not ok: break
    if i%2==0:
        ok,fr=cap.retrieve()
        out=cv2.resize(fr[172:1987,:],(OW,OH),interpolation=cv2.INTER_AREA)
        t=n/FPS
        for tc,x,y in clicks:
            u=(t-tc)/0.65
            if 0<=u<1:
                e=1-2**(-10*u);ov=out.copy()
                cv2.circle(ov,(int(x),int(y)),int(2*(10+58*e)),(255,145,50),8,cv2.LINE_AA)
                u2=(t-tc-0.08)/0.65
                if 0<=u2<1:
                    e2=1-2**(-10*u2);cv2.circle(ov,(int(x),int(y)),int(2*(8+40*e2)),(255,255,255),4,cv2.LINE_AA)
                a=0.9*(1-u)**1.6;out=cv2.addWeighted(ov,a,out,1-a,0)
        ff.stdin.write(out.tobytes());n+=1
    i+=1
ff.stdin.close();ff.wait();print("frames",n,"of src",i)
