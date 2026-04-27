#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import can
import time
import random
import argparse

# ============================================================
# 기본 설정
# ============================================================

CHANNEL          = "can0"     # 트래픽을 송신할 CAN 인터페이스
PACKET_COUNT     = 100        # 각 mode 당 전송할 (최대) 프레임 수
NORMAL_INTERVAL  = 0.05       # 50ms (20fps) → flood 탐지 안 걸리는 속도

# IDS 규칙과 맞춘 CAN ID
TIMESTAMP_ID     = 0x100
DLC_ID           = 0x200
FLOOD_ID         = 0x300
NORMAL_ID        = 0x400


def rand_bytes(n: int) -> list[int]:
    """
    n 바이트 길이의 랜덤 payload 생성
    """
    return [random.randint(0, 255) for _ in range(n)]


# ============================================================
# CAN Traffic Generator
# ============================================================
class CANGenerator:
    def __init__(self):
        # SocketCAN 인터페이스 열기
        self.bus = can.interface.Bus(
            interface="socketcan",
            channel=CHANNEL
        )
        
        # 난수로 결정된 공격 횟수를 저장할 변수 초기화
        self.timestamp_attack_count = 0
        self.dlc_attack_count = 0

    # --------------------------------------------------------
    # 1. Timestamp anomaly
    #    - payload 앞 4바이트에 시간 삽입
    #    - 과거(replay) / 미래(timestamp jump) 상황 생성
    # --------------------------------------------------------
    def send_timestamp(self):
        # PACKET_COUNT 한도 내에서 난수로 공격 횟수 결정 및 저장
        self.timestamp_attack_count = random.randint(1, PACKET_COUNT)
        
        for i in range(self.timestamp_attack_count):
            # 짝수: 과거 timestamp / 홀수: 미래 timestamp
            ts = int(time.time()) - 60 if i % 2 == 0 else int(time.time()) + 1000

            # 4B timestamp + 4B random data
            data = list(ts.to_bytes(4, "big")) + rand_bytes(4)

            msg = can.Message(
                arbitration_id=TIMESTAMP_ID,
                is_extended_id=False,
                dlc=8,
                data=data
            )
            self.bus.send(msg)
            time.sleep(NORMAL_INTERVAL)

        print(f"[*] timestamp anomaly sent ({self.timestamp_attack_count} frames)")

    # --------------------------------------------------------
    # 2. DLC mismatch (> 8)
    #    - Classic CAN 규격 위반
    # --------------------------------------------------------
    def send_dlc(self):
        # PACKET_COUNT 한도 내에서 난수로 공격 횟수 결정 및 저장
        self.dlc_attack_count = random.randint(1, PACKET_COUNT)
        
        for _ in range(self.dlc_attack_count):
            dlc = random.choice([9, 10, 11, 12])  # 불법 DLC
            data = rand_bytes(8)                  # 실제 데이터는 8바이트

            msg = can.Message(
                arbitration_id=DLC_ID,
                is_extended_id=False,
                dlc=dlc,
                data=data
            )
            self.bus.send(msg)
            time.sleep(NORMAL_INTERVAL)

        print(f"[*] DLC mismatch sent ({self.dlc_attack_count} frames)")

    # --------------------------------------------------------
    # 3. Flooding attack
    #    - 짧은 시간에 많은 프레임 송신
    # --------------------------------------------------------
    def send_flood(self):
        target = 600        # IDS flood threshold(500) 초과
        count  = 0
        start  = time.monotonic()

        while count < target:
            try:
                msg = can.Message(
                    arbitration_id=FLOOD_ID,
                    is_extended_id=False,
                    dlc=8,
                    data=rand_bytes(8)
                )
                self.bus.send(msg)
                count += 1
            except can.CanOperationError:
                # 송신 버퍼 포화 시 잠깐 대기
                time.sleep(0.0005)

        elapsed = time.monotonic() - start
        print(f"[*] flood sent: {count} frames ({count/elapsed:.0f} fps)")

    # --------------------------------------------------------
    # 4. Normal traffic
    #    - IDS false positive 확인용
    # --------------------------------------------------------
    def send_normal(self):
        for _ in range(PACKET_COUNT):
            dlc = random.randint(1, 8)
            data = rand_bytes(dlc)

            msg = can.Message(
                arbitration_id=NORMAL_ID,
                is_extended_id=False,
                dlc=dlc,
                data=data
            )
            self.bus.send(msg)
            time.sleep(NORMAL_INTERVAL)

        print("[*] normal traffic sent")

    # --------------------------------------------------------
    # 종료 처리
    # --------------------------------------------------------
    def close(self):
        # 종료 전 공격 횟수가 저장된 변수 출력
        print("\n[+] --- Attack Summary ---")
        print(f"[+] Randomized Timestamp Attacks Generated : {self.timestamp_attack_count}")
        print(f"[+] Randomized DLC Attacks Generated       : {self.dlc_attack_count}")
        print("[+] ----------------------\n")
        
        self.bus.shutdown()


# ============================================================
# Entry Point
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Classic CAN traffic generator (multi-mode)"
    )
    parser.add_argument(
        "--mode",
        nargs="+",   # 여러 mode를 순서대로 입력 가능
        choices=["timestamp", "dlc", "flood", "normal"],
        required=True,
        help="보낼 트래픽 유형 (입력한 순서대로 실행)"
    )

    args = parser.parse_args()
    gen = CANGenerator()

    try:
        # 입력된 mode를 순서대로 실행
        for mode in args.mode:
            print(f"\n[*] Executing mode: {mode}")
            if mode == "timestamp":
                gen.send_timestamp()
            elif mode == "dlc":
                gen.send_dlc()
            elif mode == "flood":
                gen.send_flood()
            elif mode == "normal":
                gen.send_normal()
    finally:
        # 항상 CAN 인터페이스 정리 및 난수 카운트 변수 출력
        gen.close()