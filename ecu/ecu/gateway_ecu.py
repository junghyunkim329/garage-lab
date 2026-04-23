#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# --------------------------------------------------
# Gateway: Physical CAN -> vCAN (FINAL, NO DEDUP)
#
#  can1  --->  vcan0  --->  vcan1 (IDS / Brake ECU)
#
#  - can0 <-> can1 : 물리 CAN (ACK 존재)
#  - vcan0/vcan1  : 가상 CAN
#  - 단방향 브리지 (loop 없음)
# --------------------------------------------------

import socket
import struct
import select
import time

# ==================================================
# SocketCAN constants
# ==================================================
SOL = socket.SOL_CAN_RAW
RAW = getattr(socket, "CAN_RAW_FILTER", 1)
FD  = getattr(socket, "CAN_RAW_FD_FRAMES", 5)
OWN = getattr(socket, "CAN_RAW_RECV_OWN_MSGS", 4)

# ==================================================
# Socket helpers
# ==================================================
def rx(iface: str):
    s = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
    s.setsockopt(SOL, RAW, struct.pack("=II", 0, 0))  # 전체 수신
    try:
        s.setsockopt(SOL, FD, 1)
        s.setsockopt(SOL, OWN, 0)
    except OSError:
        pass
    s.bind((iface,))
    return s

def tx(iface: str):
    s = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
    try:
        s.setsockopt(SOL, FD, 1)
        s.setsockopt(SOL, OWN, 0)
    except OSError:
        pass
    s.bind((iface,))
    return s

def parse_frame(f: bytes):
    can_id, dlc, data = struct.unpack("=IB3x8s", f[:16])[0:3]
    can_id &= 0x1FFFFFFF
    dlc = min(dlc, 8)
    return can_id, dlc, data[:dlc]

# ==================================================
# Interfaces
# ==================================================
rx_can1  = rx("can1")     # 물리 CAN tap
tx_vcan0 = tx("vcan0")
rx_vcan0 = rx("vcan0")
tx_vcan1 = tx("vcan1")   # IDS / Brake ECU

print("[GW] can1 -> vcan0 -> vcan1 (NO DEDUP)", flush=True)

# ==================================================
# Main loop
# ==================================================
while True:
    r, _, _ = select.select([rx_can1, rx_vcan0], [], [])

    for s in r:
        frame = s.recv(72)
        can_id, dlc, data = parse_frame(frame)

        # ----- Physical CAN -> vCAN -----
        if s is rx_can1:
            tx_vcan0.send(frame)
            print(
                time.strftime("%T"),
                f"[fwd] can1 -> vcan0 ID=0x{can_id:X} DLC={dlc}",
                flush=True
            )

        # ----- vCAN -> vCAN -----
        elif s is rx_vcan0:
            tx_vcan1.send(frame)
            print(
                time.strftime("%T"),
                f"[fwd] vcan0 -> vcan1 ID=0x{can_id:X} DLC={dlc}",
                flush=True
            )