# Compatibility import: the actual route implementation lives in domains/*/presentation/router.py.
# Add domain endpoint behavior there rather than duplicating it in this wrapper.
from app.domains.administration.presentation.router import router
