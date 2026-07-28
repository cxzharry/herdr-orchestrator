# Delivery flow reference

`assets/delivery-flow.excalidraw` is the editable semantic topology. SVG is the
canonical render source; PNG is its deterministic visual preview.

![Eight-pane Herdr delivery flow](../assets/delivery-flow.png)

- [SVG version](../assets/delivery-flow.svg)
- [Editable Excalidraw version](../assets/delivery-flow.excalidraw)

Call `view_image` on the PNG before planning. Use SVG only as a fallback.
The worker fan-out shows maximum topology, not unconditional concurrency;
runtime dependency waves decide which lanes may start.

Before delivery or after any visual edit, regenerate PNG and run:

```bash
python3 scripts/render_assets.py --write assets/delivery-flow.png
python3 scripts/verify_assets.py
```

Update Excalidraw and SVG together. The validator enforces the exact element
allowlist, canonical semantics, pinned renderer, and exact-byte PNG.
Update `assets/manifest.json` hashes and the validator's pinned canonical source
digests in the same change.
