import time

BAR_WIDTH = 20


def format_duration(seconds):
    """Format a duration as e.g. '42s', '7m05s' or '2h03m'."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


class Progress:
    """Log-friendly progress bar: one line per 5% step instead of a carriage-return bar.

    Output usually ends up in a log file or a terminal over SSH, where in-place
    updates turn into noise. Call tick() once per finished item.
    """

    def __init__(self, total, label, step_percent=5):
        self.total = total
        self.label = label
        self.done = 0
        self.start = time.monotonic()
        self.step = max(1, total * step_percent // 100)

    def tick(self):
        self.done += 1
        if self.done % self.step == 0 or self.done == self.total:
            print(self.line(), flush=True)

    def line(self):
        elapsed = time.monotonic() - self.start
        filled = BAR_WIDTH * self.done // self.total
        bar = "#" * filled + "-" * (BAR_WIDTH - filled)
        percent = 100 * self.done // self.total
        rate = self.done / elapsed if elapsed > 0 else 0
        remaining = (self.total - self.done) / rate if rate > 0 else 0
        return (f"[{self.label}] [{bar}] {self.done}/{self.total} ({percent}%) "
                f"{rate:.1f}/s, elapsed {format_duration(elapsed)}, "
                f"remaining ~{format_duration(remaining)}")
