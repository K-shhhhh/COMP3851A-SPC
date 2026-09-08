# Basic process logging shared by backend modules.
# TODO (backend): add request/job correlation and redact sensitive values from logs.
import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("spc")
