# Placeholder for logging configuration
import logging

def configure_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

if __name__ == "__main__":
    logger = configure_logging()
    logger.info("This is an info message.")
    logger.warning("This is a warning message.")
