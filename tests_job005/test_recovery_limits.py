"""Quota tests against disposable PostgreSQL only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
import os
import sys
import unittest

from sqlalchemy import create_engine, select, func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from render_recovery_limits import (
    allow_request, recovery_limits, GLOBAL_LIMIT, SOURCE_LIMIT, ORDER_LIMIT,
)

URL = os.environ.get("TEST_RECOVERY_DATABASE_URL")


@unittest.skipUnless(URL, "requires disposable PostgreSQL")
class RecoveryQuotaTests(unittest.TestCase):
    def test_limits_concurrency_and_window_reset(self):
        url = make_url(URL)
        self.assertEqual(url.drivername, "postgresql+psycopg")
        self.assertEqual(url.host, "127.0.0.1")
        self.assertEqual(url.database, "zunpy_recovery_test")
        engine = create_engine(url, connect_args={
            "options": "-c statement_timeout=10000 -c lock_timeout=5000",
        })
        self.addCleanup(engine.dispose)
        recovery_limits.create(engine)
        now = datetime(2026, 11, 26, 12, tzinfo=timezone.utc)

        def reserve(order, source, when=now):
            with Session(engine) as db, db.begin():
                return allow_request(db, order_id=order, source_key=source, now=when)

        source = "a" * 64
        for _ in range(ORDER_LIMIT - 1):
            self.assertTrue(reserve("ZJ-ONE", source))
        barrier = Barrier(2, timeout=5)
        def concurrent(s):
            barrier.wait()
            return reserve("ZJ-ONE", s)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(concurrent, ["b" * 64, "c" * 64]))
        self.assertEqual(sum(results), 1)
        self.assertFalse(reserve("zj-one", "d" * 64))

        for i in range(SOURCE_LIMIT - (ORDER_LIMIT - 1)):
            self.assertTrue(reserve("ZJ-SOURCE-" + str(i), source))
        self.assertFalse(reserve("ZJ-SOURCE-EXTRA", source))
        used = ORDER_LIMIT + SOURCE_LIMIT - (ORDER_LIMIT - 1)
        for i in range(GLOBAL_LIMIT - used):
            self.assertTrue(reserve("ZJ-GLOBAL-" + str(i), format(1000 + i, "064x")))
        self.assertFalse(reserve("ZJ-GLOBAL-EXTRA", "f" * 64))
        with Session(engine) as db:
            rows = db.execute(select(func.count()).select_from(recovery_limits)).scalar_one()
            self.assertLessEqual(rows, 1 + 2 * GLOBAL_LIMIT)
        self.assertTrue(reserve("ZJ-ONE", source, now + timedelta(minutes=15)))
        with Session(engine) as db:
            rows = db.execute(select(func.count()).select_from(recovery_limits)).scalar_one()
            self.assertEqual(rows, 3)


if __name__ == "__main__":
    unittest.main()
