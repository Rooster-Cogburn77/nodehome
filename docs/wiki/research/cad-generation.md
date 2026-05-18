# CAD Generation Watch

**Status:** Watch lane, not current implementation lane
**Last updated:** 2026-05-18

This page tracks neural CAD generation systems that may become useful for local
engineering/design experiments. The bar for adoption is higher than "runs on a
GPU": the tool needs reproducible local inference, useful output beyond demo
samples, and a clear project use case.

## GenCAD / arXiv 2409.16294

- **Source:** MIT project page, arXiv paper, and `ferdous-alam/GenCAD` GitHub repo.
- **Links:** [Project](https://gencad.github.io/), [GitHub](https://github.com/ferdous-alam/GenCAD), [arXiv](https://arxiv.org/abs/2409.16294)
- **Published:** 2025 project/paper version of arXiv `2409.16294`.
- **Confidence:** Primary artifact exists with code, Dockerfile, checkpoints, and dataset links. Local Nodehome run has not been reproduced yet.
- **What it is:** Image-conditioned CAD generation: input image/render -> learned CAD-command latent -> parametric CAD command sequence -> OpenCascade solid -> optional STL/rendered output.
- **Dataset bias:** Trained around the DeepCAD-style distribution: mostly simple sketch/extrude/revolve CAD primitives from Onshape-derived models. Expect brackets, plates, simple solids, and primitive-like geometry. Do not expect reliable reconstruction of complex assemblies or production mechanical parts from arbitrary photos.
- **Action:** Watch lane plus optional bounded lab smoke. Do not add it to Nodechat, Open WebUI, or the production serving stack.

### Honest Capability Read

GenCAD is a paper artifact and research demo, not a CAD replacement.

Useful outputs may include:

- starter geometry for simple visually described parts
- toy/research examples of image-to-parametric-CAD generation
- STL/render samples that show where neural CAD generation is headed

Not expected to work reliably:

- production-ready manufacturable parts
- accurate reverse engineering from photos
- assemblies, fasteners, tolerances, threads, fillets, or mechanical design intent
- CFD-quality rack/chassis geometry for Nodehome

The thin Nodehome connection is local GPU research and possible future
engineering-tool experiments. It is not currently useful for the Nodehome CFD
path; rack/chassis geometry should still be hand-modeled or built from measured
CAD primitives.

### Local Run Feasibility

Nodehome can likely run a smoke test:

- Docker path exists in the repo.
- Inference uses PyTorch plus `pythonocc-core` / OpenCascade.
- Headless rendering is documented through `xvfb-run`.
- Single unrestricted RTX 3090 should be enough for an inference smoke.

Expected rough flow:

```bash
git clone https://github.com/ferdous-alam/GenCAD
cd GenCAD
docker build -t gencad:latest .
```

Then run the container with a single unrestricted GPU, mount sample
images/results, and run inference inside the container:

```bash
docker run --gpus '"device=0"' -e CUDA_VISIBLE_DEVICES=0 \
  -v "$(pwd)/data/images:/app/data/images" \
  -v "$(pwd)/results:/app/results" \
  -it gencad:latest /bin/bash
```

```bash
xvfb-run --server-args="-screen 0 2048x2048x24" \
  python inference_gencad.py -image_path data/images -export_img -export_stl
```

### Known Risks

- Repo maturity: small paper artifact, no releases, low commit count. Treat as a one-time research smoke, not a dependency.
- Checkpoint fragility: pretrained models and dataset are Google Drive links. If the smoke matters, mirror checksums and local copies outside git.
- Headless CAD stack: `pythonocc-core` / OpenCascade can be finicky under `xvfb`.
- Generalization: project-page examples may be cherry-picked; out-of-distribution images are likely to produce plausible-looking but wrong primitive shapes.
- Script trust: inspect `inference_gencad.py`, Dockerfile, and dependency files before mounting anything. Use disposable mounts only.

### Lab-Only Smoke Gates

Hard gates before running:

- Use a disposable Docker container or dedicated lab directory.
- Do not mount private data, credentials, KeePass vaults, inboxes, subscriber/customer material, or production Nodehome state.
- Pin the container to one unrestricted GPU with Docker `--gpus '"device=0"'` and `CUDA_VISIBLE_DEVICES=0` unless there is a deliberate reason to use GPU1.
- Stop `vllm-server` only if needed to free GPU memory, then restart it afterward and verify the normal LLM stack recovers.
- Do not use GPU2 while the temporary pigtail rule is active.
- Keep checkpoints, dataset files, generated STLs/renders, and raw logs out of git.
- Time-box setup at 2 hours. If Docker, Google Drive downloads, CUDA/PyTorch, or OpenCascade rendering become unstable, stop and log the blocker.

### Smoke Success Criteria

A useful smoke should produce:

- at least one generated STL from a known sample image
- one rendered generated image
- notes on runtime, GPU used, peak VRAM if captured, and any OpenCascade/Xvfb errors
- honest output assessment: simple primitive match, wrong-but-plausible, or unusable

### Revisit Triggers

Re-evaluate if:

- upstream publishes releases or clearer reproducible checkpoints
- a community fork improves setup, checkpoint hosting, or output quality
- a real Nodehome use case appears for simple parametric CAD starter geometry
- a newer neural-CAD model generalizes beyond DeepCAD-style primitive shapes

Until then, GenCAD is a local research curiosity and optional toolbelt smoke,
not a production CAD workflow.
