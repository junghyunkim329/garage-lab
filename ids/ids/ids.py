import can
import time
from collections import deque

# -----------------------------
# 설정값
# -----------------------------
INPUT_CHANNEL = "can0"

FLOOD_THRESHOLD = 100     # 초당 메시지 수
TIME_WINDOW = 1.0         # 초
TIMESTAMP_TOLERANCE = 1.0 # 과거 허용 범위
DEBUG = True

# -----------------------------
# 디버그 출력 함수
# -----------------------------
def log(*args):#*arg의미 arg를 여러개 받겠다는 의미이다.
    if DEBUG:
        print("[DEBUG]", *args)

# -----------------------------
# IDS 클래스 (탐지만 수행)
# -----------------------------
class CAN_IDS:
    def __init__(self):
        self.bus = can.interface.Bus(
            interface="socketcan",
            channel=INPUT_CHANNEL
        )

        self.msg_times = deque()
        self.last_timestamp = 0

    # -----------------------------
    # 탐지 로직
    # -----------------------------
    def detect(self, msg):
        alerts = []
        now = time.time()

        
        # 메시지 요약 출력
        log("--------------------------------------------------")
        log(f"NEW MESSAGE: ID=0x{msg.arbitration_id:X}, ts={msg.timestamp}, dlc={msg.dlc}, data={msg.data}")


        # 1. Timestamp anomaly
        ts = int.from_bytes(msg.data[:4], byteorder='big', signed=False)
        now = int(time.time())

        log(f"[TS] extracted={ts}, last={self.last_timestamp}")
        # rollback 탐지
        if ts < self.last_timestamp:
            alerts.append("Timestamp rollback")
            log(f"Timestamp_anomaly_alerts======{alerts}")

        # replay 탐지
        TIMESTAMP_TOLERANCE = 5  # 초 단위 허용 범위
        if now - ts > TIMESTAMP_TOLERANCE:
            alerts.append("Replay (old timestamp)")
            log(f"Timestamp_anomaly_alerts======{alerts}")

        # 마지막 timestamp 갱신
        self.last_timestamp = ts
        log(f"RAW DATA:{list(msg.data)}")
        log(f"PARSED TS: {ts}, NOW: {now}")

        # 2. DLC mismatch
        log(f"msg.dlc_data======{msg.dlc}, msg.data_actual======{len(msg.data)}")

        if msg.dlc is not None and msg.data is not None:
            if msg.dlc != len(msg.data):
                alerts.append("DLC mismatch")
        
        log(f"DLC_mismatch_alerts======{alerts}")

        # 3. Flooding detection
        log(f"[FLOOD] deque size={len(self.msg_times)}, window={list(self.msg_times)}")
        
        self.msg_times.append(now)

        while self.msg_times and (now - self.msg_times[0]) > TIME_WINDOW:
            removed = self.msg_times.popleft()#오래된 기록은 빠르게 제거할랜다.
            log(f"[FLOOD] old timestamp removed: {removed}")

        if len(self.msg_times) > FLOOD_THRESHOLD:
            alerts.append("Flooding")
            log("[FLOOD ALERT] Flooding detected!!")
        return alerts
        
    
    # -----------------------------
    # 실행 루프
    # -----------------------------
    def run(self):
        print("[*] IDS (Detection Only) started")

        while True:
            msg = self.bus.recv()

            if msg is None:
                continue

            alerts = self.detect(msg)

            log(f"[RESULT] alerts={alerts}")
            if alerts:
                print(f"[ALERT] {alerts} | ts={msg.timestamp} dlc={msg.dlc}")

# -----------------------------
# 실행
# -----------------------------
if __name__ == "__main__":
    ids = CAN_IDS()
    ids.run()