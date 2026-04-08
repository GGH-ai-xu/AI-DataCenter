import logging
import os
import sys
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.logging_config import configure_application_logging  # noqa: E402


class LoggingConfigTests(unittest.TestCase):
    def test_asyncssh_logger_is_demoted_to_warning(self):
        asyncssh_logger = logging.getLogger("asyncssh")
        original_level = asyncssh_logger.level

        try:
            asyncssh_logger.setLevel(logging.NOTSET)
            configure_application_logging()
            self.assertEqual(asyncssh_logger.level, logging.WARNING)
        finally:
            asyncssh_logger.setLevel(original_level)


if __name__ == "__main__":
    unittest.main()
