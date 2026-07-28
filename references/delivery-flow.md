# Delivery flow reference

`assets/delivery-flow.excalidraw` is the editable semantic topology. SVG is the
canonical render source; PNG is its deterministic visual preview.

![Nine-pane Herdr delivery flow](../assets/delivery-flow.png)

- [SVG version](../assets/delivery-flow.svg)
- [Editable Excalidraw version](../assets/delivery-flow.excalidraw)

Call `view_image` on the PNG before planning. Use SVG only as a fallback.

The graph shows the maximum nine-pane topology, not unconditional concurrency:

- P2-P5 start only in dependency-ready waves.
- P5 restarts as Integration Owner before publishing.
- P5 smoke and P6 Integration Review run in parallel.
- Their PASS receipts release DEV or the sole environment; without a deployment
  target, P5 starts a local review runtime.
- P7-P9 prepare early, then run applicable review concurrently and report to P1
  as each finishes.
- Main promotion waits only for applicable blocking gates.

Before delivery or after a visual edit, regenerate PNG and run:

```bash
python3 scripts/render_assets.py --write assets/delivery-flow.png
python3 scripts/verify_assets.py
```

Update Excalidraw and SVG together. The validator enforces canonical elements,
node order, bound arrows, role colors, pinned renderer, and exact-byte PNG.
Update `assets/manifest.json` and pinned source digests in the same change.
