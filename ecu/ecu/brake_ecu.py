#brake_ecu.py
import socket, struct, time, select
SOL=socket.SOL_CAN_RAW
s=socket.socket(socket.PF_CAN,socket.SOCK_RAW,socket.CAN_RAW)
s.setsockopt(SOL, getattr(socket,"CAN_RAW_FILTER",1), struct.pack("=II",0,0))  # 전체 허용(네 커널 조합에서 필수)
try: s.setsockopt(SOL, getattr(socket,"CAN_RAW_FD_FRAMES",5), 1)
except OSError: pass
try: s.setsockopt(SOL, getattr(socket,"CAN_RAW_RECV_OWN_MSGS",4), 0)  # 자기수신 끔(중복 억제)
except OSError: pass
s.bind(("vcan1",)); print("[Brake] vcan2", flush=True)
while True:
    r,_,_=select.select([s],[],[],1.0)
    if not r: continue
    f=s.recv(72)
    can_id,dlc,data=struct.unpack("=IB3x8s",f[:16]); can_id&=0x1FFFFFFF; data=data[:dlc]
    print(f"{time.strftime('%T')} ID=0x{can_id:03X} DLC={dlc} DATA=[{' '.join(f'{b:02X}' for b in data)}]", flush=True)
