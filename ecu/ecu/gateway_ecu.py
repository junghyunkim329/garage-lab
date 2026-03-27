# ------------------------------------------------------------
# Gateway ECU (2-hop): can0 -> can1(loopback RX) -> vcan2
# * IDS 실험용 순수 패스스루 버전 *
# ------------------------------------------------------------
# 포함 기능:
#   - 2-Hop 체인 (can0 → can1 → vcan2)
#   - can1 loopback(True)로 소프트웨어 RX 이벤트 생성
#   - dedup(5ms) 적용 → TX+echo 중복 제거
#   - JSON 로깅 (forward / dedup / error)
#   - 콘솔 로그 SHOW_LOG 스위치
#
# 제거 기능:
#   - 메시지 필터링(정책) 전부 제거
#   - policy.json 로딩 제거
#   - decide_action() 제거
#   - drop(reason=default/policy) 제거
# ------------------------------------------------------------

import socket, struct, select, time, sys, json, threading, os

# ------- SocketCAN 옵션 번호 -------
SOL  = socket.SOL_CAN_RAW
RAW  = getattr(socket, "CAN_RAW_FILTER", 1)
FD   = getattr(socket, "CAN_RAW_FD_FRAMES", 5)
OWN  = getattr(socket, "CAN_RAW_RECV_OWN_MSGS", 4)
LOOP = getattr(socket, "CAN_RAW_LOOPBACK", 3)

# ------- 튜닝 파라미터 -------
DEDUP_MS = 5.0e-3             # dedup 창(5ms) : 초기 중복 2회 방지 안정값
TXV2_LB  = True               # True=관찰 모드(candump vcan2에도 보임)
SHOW_LOG = True              # 콘솔 print on/off
LOG_PATH = "/tmp/gw_events.jsonl"
# -----------------------------

# ------- JSON 로깅 -------
class JsonlLogger:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        d = os.path.dirname(path)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
    def write(self, ev: dict):
        ev["_ts"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
        line = json.dumps(ev, ensure_ascii=False, separators=(",",":"))
        with self.lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

logger = JsonlLogger(LOG_PATH)

# ------- 소켓 rx/tx -------
def rx(iface: str) -> socket.socket:
    s = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
    s.setsockopt(SOL, RAW, struct.pack("=II", 0, 0))    # ALL PASS (필수)
    try:
        s.setsockopt(SOL, FD, 1)
        s.setsockopt(SOL, OWN, 0)                       # 자기 송신 미수신
    except OSError:
        pass
    s.bind((iface,))
    return s

def tx(iface: str, lb=True) -> socket.socket:
    s = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
    try:
        s.setsockopt(SOL, FD, 1)
        s.setsockopt(SOL, LOOP, 1 if lb else 0)         # ★ can1은 lb=True → 소프트 RX 생성
    except OSError:
        pass
    s.bind((iface,))
    return s

# ------- 체인 구성 -------
rx0  = rx("can0")
tx1  = tx("can1", lb=True)    # ★ hop1: can1에 소프트웨어 RX 생성
rx1  = rx("can1")
txv2 = tx("vcan2", TXV2_LB)

# ------- 프레임 파서 & dedup -------
def parse_frame(f: bytes):
    can_id, dlc, data = struct.unpack("=IB3x8s", f[:16])[0:3]
    can_id &= 0x1FFFFFFF
    return can_id, min(dlc, 8), data[:dlc]

_last = {}
def is_dup(src: str, frame: bytes) -> bool:
    can_id, dlc, data = struct.unpack("=IB3x8s", frame[:16])[0:3]
    can_id &= 0x1FFFFFFF
    key = (src, can_id, dlc, bytes(data[:dlc]))
    now = time.monotonic()
    prev = _last.get(key)
    _last[key] = now
    return (prev is not None) and ((now - prev) < DEDUP_MS)

def brief(tag, msg):
    if SHOW_LOG:
        print(time.strftime("%T"), tag, msg, flush=True)

print("[GW] 2-Hop Gateway (no filtering)  (can0 -> can1 -> vcan2)", flush=True)

# ------- 메인루프 -------
try:
    while True:
        r,_,_ = select.select([rx0, rx1], [], [], 1.0)
        for s in r:
            frame = s.recv(72)
            in_iface = "can0" if s is rx0 else "can1"

            # (1) dedup
            if is_dup(in_iface, frame):
                logger.write({"event":"drop","reason":"dedup","in_iface":in_iface})
                brief("[dedup]", f"in={in_iface} drop")
                continue

            # (2) 파싱만 (필터 없음)
            can_id, dlc, data = parse_frame(frame)

            # (3) forward만 수행 (정책 없음)
            if in_iface == "can0":
                try:
                    tx1.send(frame)
                    brief("[fwd]", f"can0->can1 ID=0x{can_id:03X} DLC={dlc}")
                    logger.write({"event":"forward","in_iface":"can0",
                                  "out_ifaces":["can1"],"id":can_id,
                                  "dlc":dlc,"data_hex":data.hex()})
                except OSError as e:
                    logger.write({"event":"error","iface":"can1","err":str(e)})
                    brief("[error]", f"send_fail can1 {e}")

            elif in_iface == "can1":
                try:
                    txv2.send(frame)
                    brief("[fwd]", f"can1->vcan2 ID=0x{can_id:03X} DLC={dlc}")
                    logger.write({"event":"forward","in_iface":"can1",
                                  "out_ifaces":["vcan2"],"id":can_id,
                                  "dlc":dlc,"data_hex":data.hex()})
                except OSError as e:
                    logger.write({"event":"error","iface":"vcan2","err":str(e)})
                    brief("[error]", f"send_fail vcan2 {e}")

except KeyboardInterrupt:
    print("[GW] stopped", file=sys.stderr)