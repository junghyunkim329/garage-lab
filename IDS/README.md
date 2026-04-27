## gen.py

Classic CAN Generator — Multi‑Mode Selectable

기능:

- Timestamp anomaly (replay / future)
- DLC > 8 (Classic CAN protocol violation)
- Flooding attack
- Normal traffic

특징:

- `--mode` 옵션으로 여러 트래픽을 순서대로 실행 가능
  <br/>예) --mode timestamp normal dlc flood
