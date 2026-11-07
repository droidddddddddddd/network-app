"""Release feature gates; default off in every environment."""
import os


def wallet_features_enabled():
    return os.getenv("ENABLE_WALLET_FEATURES", "0").strip() == "1"
