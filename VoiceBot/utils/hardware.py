import os
import sounddevice as sd
from utils.logger import get_logger

logger = get_logger(__name__)

def is_safe_for_barge_in() -> bool:
    """
    Checks if it's safe to enable Full-Duplex Barge-in without acoustic feedback loops.
    Returns True if HEADSET_MODE is True in config, False otherwise.
    """
    from config import Config
    import os
    
    if os.getenv("FORCE_BARGE_IN", "false").lower() == "true":
        logger.warning("[Warning] FORCE_BARGE_IN is enabled! Proceeding with full duplex regardless of hardware.", extra={"markup": True})
        return True
        
    if os.getenv("FORCE_BARGE_IN", "").lower() == "false":
        logger.warning("[Warning] FORCE_BARGE_IN is explicitly false. Operating in Walkie-Talkie mode.", extra={"markup": True})
        return False
        
    if Config.HEADSET_MODE:
        logger.info("[Success] HEADSET_MODE=True detected in config. Full-Duplex Barge-in enabled.", extra={"markup": True})
        return True
        
    logger.warning("[Warning] HEADSET_MODE is False. Operating in safe Walkie-Talkie mode to prevent echoes.", extra={"markup": True})
    return False
