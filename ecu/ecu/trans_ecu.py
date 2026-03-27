import socket, struct
SOL  = socket.SOL_CAN_RAW
LOOP = getattr(socket, "CAN_RAW_LOOPBACK", 3)
s = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
s.setsockopt(SOL, LOOP, 0)              # 송신 소켓의 소켓 루프백 OFF → can0 중복 크게 감소
s.bind(("can0",))
frame = struct.pack("=IB3x8s", 0x321, 1, b'\x05'+b'\x00'*7)
s.send(frame)
print("sent once (no socket loopback)")
