"""Logging and error handling shared by the build scripts.

Every run writes a timestamped log under logs/ containing the decisions the build made
(danger floor, scaling factors, item counts) and, if something fails, the full traceback
plus the local variables of the failing frame. That is usually enough to diagnose a bug
without reproducing it.
"""
import datetime
import logging
import os
import sys
import traceback

import paths
LOG_DIR = paths.log_dir()
_log = None


def setup(name="build", verbose=True):
    """Console + file logging. Returns the logger."""
    global _log
    os.makedirs(LOG_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(LOG_DIR, f"{name}-{stamp}.log")
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    logger.addHandler(fh)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO if verbose else logging.WARNING)
    ch.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ch)

    logger.debug("python %s", sys.version.replace("\n", " "))
    logger.debug("cwd %s", os.getcwd())
    logger.debug("argv %s", sys.argv)
    logger.info("log: %s", path)
    _log = logger
    logger.log_path = path
    return logger


def get():
    return _log if _log is not None else setup()


def _dump_frame_locals(tb, logger):
    """Log the locals of the deepest frame - usually where the bad value is."""
    while tb.tb_next:
        tb = tb.tb_next
    frame = tb.tb_frame
    logger.error("failing frame: %s() in %s:%d",
                 frame.f_code.co_name, frame.f_code.co_filename, tb.tb_lineno)
    for k, v in list(frame.f_locals.items()):
        try:
            text = repr(v)
        except Exception:
            text = "<unreprable>"
        if len(text) > 300:
            text = text[:300] + f"... ({len(text)} chars)"
        logger.error("    %-24s = %s", k, text)


def run(fn, *args, name="build", **kwargs):
    """Call fn, logging success or a diagnosable failure. Returns fn's result or exits 1."""
    logger = setup(name)
    try:
        result = fn(*args, **kwargs)
    except Exception as exc:                       # noqa: BLE001 - we want everything
        logger.error("BUILD FAILED: %s: %s", type(exc).__name__, exc)
        logger.error("%s", "".join(traceback.format_exception(type(exc), exc,
                                                              exc.__traceback__)))
        _dump_frame_locals(exc.__traceback__, logger)
        logger.error("")
        logger.error("Nothing was installed. Full details in: %s", logger.log_path)
        sys.exit(1)
    logger.info("done. log: %s", logger.log_path)
    return result
