import os
import sounddevice as sd
from utils.logger import get_logger

logger = get_logger(__name__)

def is_safe_for_barge_in() -> bool:
    """
    Queries sounddevice for the active output device to determine if it's safe 
    to enable Full-Duplex Barge-in without acoustic feedback loops.
    Returns True if headphones/headset are detected, False otherwise.
    """
    if os.getenv("FORCE_BARGE_IN", "false").lower() == "true":
        logger.warning("[Warning] FORCE_BARGE_IN is enabled! Proceeding with full duplex regardless of hardware.", extra={"markup": True})
        return True
        
    try:
        device_info = sd.query_devices(sd.default.device[1])
        name = device_info['name'].lower()
        
        safe_keywords = ['headphone', 'headset', 'airpod', 'bluetooth', 'earbud']
        
        for keyword in safe_keywords:
            if keyword in name:
                logger.info(f"[Success] '{device_info['name']}' detected. Full-Duplex Barge-in enabled.", extra={"markup": True})
                return True
                
        logger.warning(f"[Warning] '{device_info['name']}' detected. Operating in safe Walkie-Talkie mode to prevent echoes. You can bypass this by setting FORCE_BARGE_IN=true in your .env", extra={"markup": True})
        return False
        
    except Exception as e:
        logger.error(f"Failed to detect hardware: {e}. Defaulting to Walkie-Talkie mode.")
        return False
