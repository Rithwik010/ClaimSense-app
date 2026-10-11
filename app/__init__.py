"""ClaimSense application package.

No telemetry from the libraries (D-PROC-4, D-PROC-5). Set here, before anything imports them:
importing `qdrant_client` imports fastembed and so onnxruntime, which starts a telemetry thread
that uploads usage events to Microsoft (and can abort the process at exit) unless
ORT_DISABLE_TELEMETRY is set when it loads. Hugging Face's hub client is told the same.
"""

import os

os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
