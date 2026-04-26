## 실행 명령어

CAN 환경 초기화 (항상 맨 처음 1번만 실행)

```shell
pkill -f python3 2>/dev/null || true

sudo cangw -F

sudo ip link del vcan2 2>/dev/null || true
sudo modprobe vcan
sudo ip link add vcan2 type vcan
sudo ip link set vcan2 up

sudo ip link set can0 down
sudo ip link set can1 down
sudo ip link set can0 type can bitrate 500000 loopback on
sudo ip link set can1 type can bitrate 500000 loopback on
sudo ip link set can0 up
sudo ip link set can1 up
```
