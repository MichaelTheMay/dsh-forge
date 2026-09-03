"""Test-only adapters that exercise launcher lifecycle without requiring Apptainer."""

import os


class FakeCellSandbox:
    ready = True
    image_digest = "a" * 64

    def status(self):
        return {
            "mode": "fake-apptainer-cell-v1",
            "ready": True,
            "reason": "test adapter",
            "image_sha256": self.image_digest,
            "hostile_code_isolation": False,
            "resource_limits": {
                "cpus": "2", "memory": "1G", "pids": 64,
                "wall_seconds": 600, "probe_required": True,
            },
        }

    def cell_plan(self, *, tree, surface, task, port, profile, network, gpu, **_options):
        argv = [tree["real_exe"]]
        if tree.get("real_node"):
            argv.insert(0, tree["real_node"])
        if surface == "headless":
            argv.extend(["headless", task])
        else:
            argv.extend(["web", "--host", "127.0.0.1", "--port", str(port), "--no-open"])
        return {
            "argv": argv,
            "environment": {"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
            "network": network,
            "gpu": "allocated" if gpu else "none",
            "image_sha256": self.image_digest,
            "executable_sha256": tree.get("executable_sha256") or "b" * 64,
            "command_sha256": "c" * 64,
            "resources": {
                "cpu": "2", "gpu": "allocated" if gpu else "none", "ram": "1G",
                "pids": 64, "wall_seconds": 600, "enforced": True,
                "note": "test adapter",
            },
            "secrets_forwarded": False,
        }
