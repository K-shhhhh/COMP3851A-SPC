"""Configure basic process logging shared by backend modules.

Request and job correlation plus sensitive-value redaction remain staging work.
"""

import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("spc")
