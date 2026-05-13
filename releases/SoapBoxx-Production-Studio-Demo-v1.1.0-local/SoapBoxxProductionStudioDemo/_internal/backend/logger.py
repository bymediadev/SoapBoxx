# backend/logger.py
import logging


class Logger:
    def __init__(self, log_file="soapboxx.log"):
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )
        self.logger = logging.getLogger("SoapBoxx")

    def log_error(self, message):
        self.logger.error(message)

    def log_ui_bug(self, message):
        self.logger.warning(f"UI Bug: {message}")

    def log_audio_issue(self, message):
        self.logger.warning(f"Audio Issue: {message}")


# Example usage
if __name__ == "__main__":
    log = Logger()
    log.log_error("API failed to respond.")
    log.log_ui_bug("Button not clickable.")
    log.log_audio_issue("Audio buffer underrun.")
