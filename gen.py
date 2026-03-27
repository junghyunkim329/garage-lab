import can
import time
import random
import argparse

# -----------------------------
# 설정
# -----------------------------
CHANNEL = "can0"

# -----------------------------
# Generator 클래스
# -----------------------------
class CANGenerator:
    def __init__(self):
        self.bus = can.interface.Bus(
            interface="socketcan",
            channel=CHANNEL
        )

    # -----------------------------
    # 1. Timestamp 변조 패킷
    # -----------------------------
    def send_timestamp_anomaly(self, count=100):
        for _ in range(count):
            # 현재 시간 ± 랜덤 오프셋
            offset = random.uniform(-5, 5) + random.random()
            fake_ts = int(time.time() + offset)

            ts_bytes = fake_ts.to_bytes(4,byteorder='big',signed=False)

            rand_bytes = [random.randint(0,255) for _ in range(4)]
            msg = can.Message(
                arbitration_id=0x100,
                is_extended_id=False,
                dlc=8,
                data=list(ts_bytes) + rand_bytes,
            )

            self.bus.send(msg)
            time.sleep(0.05)

    # -----------------------------
    # 2. DLC mismatch 패킷
    # -----------------------------
    def send_dlc_mismatch(self, count=100):
        for _ in range(count):
            data = [0x11, 0x22]  # 실제 길이 2

            msg = can.Message(
                arbitration_id=0x200,
                is_extended_id=False,
                dlc=random.randint(3,9),  # 고의 불일치
                data=data
            )

            self.bus.send(msg)
            time.sleep(0.05)

    # -----------------------------
    # 3. Flooding 공격
    # -----------------------------
    def send_flood(self, duration=5):
        start = time.time()

        while time.time() - start < duration:
            msg = can.Message(
                arbitration_id=0x300,
                is_extended_id=False,
                dlc=8,
                data=[0xFF] * 8
            )

            self.bus.send(msg)
            # sleep 없음 → 최대 속도

    # -----------------------------
    # 4. 정상 패킷
    # -----------------------------
    def send_normal(self, count=100):
        for _ in range(count):
            dlc = random.randint(0, 8)
            data = [random.randint(0, 255) for _ in range(dlc)]

            msg = can.Message(
                arbitration_id=0x400,
                is_extended_id=False,
                dlc=dlc,
                data=data
            )

            self.bus.send(msg)
            time.sleep(0.1)


# -----------------------------
# 실행
# -----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["timestamp", "dlc", "flood", "normal"],
        required=True,
        help="트래픽 유형 선택"
    )

    args = parser.parse_args()

    gen = CANGenerator()

    if args.mode == "timestamp":
        print("[*] Sending timestamp anomaly packets")
        gen.send_timestamp_anomaly()

    elif args.mode == "dlc":
        print("[*] Sending DLC mismatch packets")
        gen.send_dlc_mismatch()

    elif args.mode == "flood":
        print("[*] Sending flooding packets")
        gen.send_flood()

    elif args.mode == "normal":
        print("[*] Sending normal packets")
        gen.send_normal()