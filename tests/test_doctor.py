from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from agent_workflow.doctor import _archive_commands_supported


class DoctorTests(unittest.TestCase):
    @patch("agent_workflow.doctor.subprocess.run")
    def test_archive_ready_requires_deterministic_tar_options(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            ["tar", "--help"],
            0,
            stdout="--sort --mtime --owner --group --numeric-owner",
            stderr="",
        )
        self.assertTrue(
            _archive_commands_supported(
                {"tar": "/usr/bin/tar", "zstd": "/usr/bin/zstd"}
            )
        )

        run.return_value = subprocess.CompletedProcess(
            ["tar", "--help"], 0, stdout="plain tar", stderr=""
        )
        self.assertFalse(
            _archive_commands_supported(
                {"tar": "/usr/bin/tar", "zstd": "/usr/bin/zstd"}
            )
        )
        self.assertFalse(
            _archive_commands_supported({"tar": "/usr/bin/tar", "zstd": None})
        )
