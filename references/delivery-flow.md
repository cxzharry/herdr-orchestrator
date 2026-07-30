# Delivery Flow

The graph in `assets/delivery-flow.png` shows the fixed-role runtime:

```text
Approved plan
  -> P1 claim or same-workspace forward
  -> atomic controller tick
       -> P2/P3/P4 fixed warm implementation slots
       -> ownership queue / capacity queue
  -> immutable receipts
  -> Compact verifier OR Standard P5 integration
  -> P6 review -> conditional P7/P8/P9
  -> P5 install/push/deploy

Herdr live state -> workspace watcher -> event queue -> P1 wake
workspace-state.json -> controller tick
```

P1 is labeled `p1_orchestrator`; P2-P9 use fixed role names. Task summary is
drawn beside a slot, never inside its role name. The same-workspace boundary
blocks foreign adoption, and recovery says it must never close user panes.
