#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# CAN IDS: flood / timestamp anomaly / DLC mismatch

import can
import time
from collections import defaultdict, deque

# ==========================================
# 설정값
# ==========================================
INPUT_CHANNEL        = "can0"
FLOOD_THRESHOLD      = 500
TIME_WINDOW          = 1.0
TIMESTAMP_TOLERANCE  = 10.0

TIMESTAMP_CHECK_IDS  = {0x100}
IS_CAN_FD            = False


class CAN_IDS:
    def __init__(self, is_fd: bool = IS_CAN_FD):
        self.bus    = self._connect()
        self.is_fd  = is_fd

        self._id_times:        dict[int, deque] = defaultdict(
            lambda: deque(maxlen=FLOOD_THRESHOLD + 200)
        )
        self._last_payload_ts: dict[int, int]   = defaultdict(int)

        # 통계
        self._total    = 0
        self._normal   = 0
        self._abnormal = 0

        # 이상 유형별 통계
        self._alert_stats = {
            "timestamp": 0,
            "dlc": 0,
            "flood": 0,
        }

    # ------------------------------------------
    # 연결 / 재연결
    # ------------------------------------------
    def _connect(self) -> can.BusABC:
        while True:
            try:
                bus = can.interface.Bus(
                    interface="socketcan",
                    channel=INPUT_CHANNEL,
                    receive_own_messages=False,
                )
                print(f"[*] IDS listening on {INPUT_CHANNEL}")
                return bus
            except Exception as e:
                print(f"[!] Connect failed: {e} — retry in 2s")
                time.sleep(2)

    def _reconnect(self):
        try:
            self.bus.shutdown()
        except Exception:
            pass
        time.sleep(1)
        self.bus = self._connect()

    # ------------------------------------------
    # 탐지 로직
    # ------------------------------------------
    def detect(self, msg: can.Message) -> list[str]:
        alerts   = []
        arb_id   = msg.arbitration_id
        now_mono = time.monotonic()

        # ── 1. Timestamp anomaly ──────────────────────────────────────────
        if arb_id in TIMESTAMP_CHECK_IDS and len(msg.data) >= 4:
            payload_ts = int.from_bytes(msg.data[:4], byteorder="big", signed=False)
            last_ts    = self._last_payload_ts[arb_id]
            now_sys    = int(time.time())
            diff       = now_sys - payload_ts       # 양수: 과거, 음수: 미래

            if diff > TIMESTAMP_TOLERANCE:
                alerts.append(f"Timestamp too old ({diff}s ago)")
                self._alert_stats["timestamp"] += 1
            elif diff < -TIMESTAMP_TOLERANCE:
                alerts.append(f"Timestamp in future ({-diff}s ahead)")
                self._alert_stats["timestamp"] += 1

            if not alerts:
                self._last_payload_ts[arb_id] = payload_ts

        # ── 2. DLC > 8 (Classic CAN) ─────────────────────────────────────
        max_dlc = 64 if self.is_fd else 8
        if msg.dlc > max_dlc:
            alerts.append(f"Invalid DLC ({msg.dlc} > {max_dlc})")
            self._alert_stats["dlc"] += 1

        # ── 3. Flooding ───────────────────────────────────────────────────
        q = self._id_times[arb_id]
        q.append(now_mono)
        while q and (now_mono - q[0]) > TIME_WINDOW:
            q.popleft()

        if len(q) > FLOOD_THRESHOLD:
            alerts.append(f"Flooding ({len(q)} frames/s)")
            self._alert_stats["flood"] += 1

        return alerts

    # ------------------------------------------
    # 메인 루프
    # ------------------------------------------
    def _print_summary(self):
        print(
            f"\n{'─'*48}\n"
            f"  총 수신   {self._total:>6} 패킷\n"
            f"  정상      {self._normal:>6} 패킷\n"
            f"  이상 탐지 {self._abnormal:>6} 패킷\n"
            f"{'─'*48}\n"
            f"  ─ 이상 유형별 통계 ─\n"
            f"  Timestamp      {self._alert_stats['timestamp']:>6}\n"
            f"  DLC            {self._alert_stats['dlc']:>6}\n"
            f"  Flood          {self._alert_stats['flood']:>6}\n"
            f"{'─'*48}"
        )

    def run(self):
        print("[*] IDS started — Ctrl+C to stop\n")
        consecutive_errors = 0

        try:
            while True:
                try:
                    msg = self.bus.recv(timeout=0.1)
                    if msg is None:
                        continue

                    consecutive_errors = 0
                    self._total += 1
                    alerts = self.detect(msg)

                    if alerts:
                        self._abnormal += 1
                        # 수신 시각은 msg.timestamp(POSIX) 사용, 없으면 현재 시각
                        ts   = msg.timestamp or time.time()
                        tstr = time.strftime("%H:%M:%S", time.localtime(ts))
                        for alert in alerts:
                            print(
                                f"[{tstr}] ALERT  {alert}"
                                f"  |  ID=0x{msg.arbitration_id:X}"
                                f"  DLC={msg.dlc}",
                                flush=True,
                            )
                    else:
                        self._normal += 1

                except can.CanOperationError as e:
                    consecutive_errors += 1
                    if consecutive_errors >= 5:
                        print(f"[!] Bus error x5, reconnecting... ({e})")
                        self._reconnect()
                        consecutive_errors = 0

                except can.CanError:
                    pass

        except KeyboardInterrupt:
            pass
        finally:
            self.bus.shutdown()
            self._print_summary()


if __name__ == "__main__":
    ids = CAN_IDS()
    ids.run()