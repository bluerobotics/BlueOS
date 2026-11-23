# BlueOS e2e tests

End-to-end tests that run a full BlueOS (bootstrap + core) in different targets (QEMU VM, real hardware).

## Requirements

- `docker`, `qemu-img`, `qemu-system-x86_64`, `ssh`, `sshpass`
- `uv`
- `/dev/kvm` (without it the VM runs, but very slowly)

## Build the VM image

The tests need the VM disk image at `.cache/sil.qcow2`. Build it once, and again whenever `targets/sil/image/` changes:

```bash
cd tests/e2e
./targets/sil/image/build.sh
```

## Run the tests

```bash
cd tests/e2e
cp env.example .env              # choose the BlueOS images under test
uv run --env-file .env pytest
uv run --env-file .env pytest scenarios/core -v
```

`E2E_CORE_IMAGE` and `E2E_BOOTSTRAP_IMAGE` select the images. Defaults are the `master` tags. Missing images are pulled
and loaded into the VM.

## Test a local BlueOS build

Build the core image from this checkout and point the tests to it:

```bash
docker build --platform linux/amd64 \
  --build-arg GIT_DESCRIBE_TAGS=$(git describe --tags --long --always) \
  --build-arg VITE_APP_GIT_DESCRIBE=$(git describe --long --always --dirty --all) \
  --tag blueos-core:dev --file core/Dockerfile core
```

Run it from the repository root. Then set it in `tests/e2e/.env`:

```
E2E_CORE_IMAGE=blueos-core:dev
```

## Run the VM only

Starts the VM without running tests, to use BlueOS VM interactively:

```bash
cd tests/e2e
uv run --env-file .env python -m targets.sil
```

It prints the URLs when BlueOS is ready and opens a Python prompt with the running VM as `target`. Press Ctrl+D to stop
the VM.

Here is an example of how to use the interactive prompt:

```python
>>> from blueos.core import BlueOS
>>> BlueOS(target.base_url).version()
>>> print(target.shell("sudo docker ps"))
```

Per-run files (disk overlay, `qemu.pid`, `serial.log`, `startup.json`) are in `.run/`. Changes made inside the VM are
lost when it stops.

## Run the frontend tests on the VM

The tests expect a Navigator by default. `E2E_BOARD=none` is for the VM, which has no board, so the tests set up SITL:

```bash
cd tests/e2e
E2E_BOARD=none uv run --env-file .env python -m targets.sil -- bun --cwd ../../e2e e2e
```
