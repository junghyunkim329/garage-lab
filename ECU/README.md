## 실행 명령어

CAN 환경 초기화 (항상 맨 처음 1번만 실행)

```shell
# vcan 모듈 로드
sudo modprobe vcan

# 기존 vcan 있으면 제거
sudo ip link del vcan0 2>/dev/null || true
sudo ip link del vcan1 2>/dev/null || true

# vcan 생성
sudo ip link add vcan0 type vcan
sudo ip link add vcan1 type vcan

# up
sudo ip link set vcan0 up
sudo ip link set vcan1 up

ip link show vcan0
ip link show vcan1

sudo ip link set can0 down
sudo ip link set can1 down

sudo ip link set can0 type can bitrate 500000 loopback off
sudo ip link set can1 type can bitrate 500000 loopback off

sudo ip link set can0 up
sudo ip link set can1 up
```
