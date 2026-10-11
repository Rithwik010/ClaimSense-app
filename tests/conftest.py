"""Shared test setup: importing `app` turns library telemetry off (D-PROC-5) before any test
module imports qdrant_client, fastembed or onnxruntime."""

import app  # noqa: F401
