import threading

from nose.tools import eq_

from zktools.tests import TestBase


class TestLocking(TestBase):
    def makeOne(self, *args, **kwargs):
        from zktools.locking import ZkLock
        return ZkLock(self.conn, *args, **kwargs)

    def setUp(self):
        if self.conn.exists('/ZktoolsLocks/zkLockTest'):
            self.conn.delete('/ZktoolsLocks/zkLockTest')

    def testBasicLock(self):
        lock = self.makeOne('zkLockTest')
        lock.clear()
        eq_(bool(lock.acquire()), True)
        eq_(lock.release(), True)

    def testLockRelease(self):
        lock1 = self.makeOne('zkLockTest')
        lock2 = self.makeOne('zkLockTest')

        vals = []

        def run():
            with lock2.acquire():
                vals.append(2)
        waiter = threading.Thread(target=run)
        lock1.acquire()
        waiter.start()
        eq_(vals, [])
        lock1.release()
        waiter.join()
        eq_(vals, [2])


class TestSharedLocks(TestLocking):
    def makeWriteLock(self, *args, **kwargs):
        from zktools.locking import ZkWriteLock
        return ZkWriteLock(self.conn, *args, **kwargs)

    def makeReadLock(self, *args, **kwargs):
        from zktools.locking import ZkReadLock
        return ZkReadLock(self.conn, *args, **kwargs)

    def testLockQueue(self):
        r1 = self.makeReadLock('zkLockTest')
        r2 = self.makeReadLock('zkLockTest')
        w1 = self.makeWriteLock('zkLockTest')

        vals = []

        def reader():
            with r2.acquire():
                vals.append('r')

        def writer():
            with w1.acquire():
                vals.append('w')

        read2 = threading.Thread(target=reader)
        write1 = threading.Thread(target=writer)
        r1.acquire()
        eq_(r1.has_lock(), True)
        read2.start()
        write1.start()
        read2.join()
        eq_(vals, ['r'])
        r1.release()
        write1.join()
        eq_(vals, ['r', 'w'])

    def testRevoked(self):
        from zktools.locking import IMMEDIATE
        w1 = self.makeReadLock('zkLockTest')
        r1 = self.makeWriteLock('zkLockTest')
        ev = threading.Event()
        vals = []

        def reader():
            with r1.acquire():
                ev.set()
                vals.append(1)
                val = 0
                while not r1.revoked():
                    val += 1

        def writer():
            with w1.acquire(revoke=IMMEDIATE):
                vals.append(2)

        reader = threading.Thread(target=reader)
        writer = threading.Thread(target=writer)
        reader.start()
        ev.wait()
        eq_(vals, [1])
        writer.start()
        reader.join()
        writer.join()
        eq_(vals, [1, 2])

    def testGentleRevoke(self):
        w1 = self.makeReadLock('zkLockTest')
        r1 = self.makeWriteLock('zkLockTest')
        ev = threading.Event()
        vals = []

        def reader():
            with r1.acquire():
                ev.set()
                vals.append(1)
                val = 0
                while not r1.revoked():
                    val += 1

        def writer():
            with w1.acquire(revoke=True):
                vals.append(2)

        reader = threading.Thread(target=reader)
        writer = threading.Thread(target=writer)
        reader.start()
        ev.wait()
        eq_(vals, [1])
        writer.start()
        reader.join()
        writer.join()
        eq_(vals, [1, 2])

    def testTimeOut(self):
        w1 = self.makeReadLock('zkLockTest')
        r1 = self.makeWriteLock('zkLockTest')

        vals = []
        ev = threading.Event()

        def reader():
            with r1.acquire():
                ev.set()
                vals.append(1)
                val = 0
                while not r1.revoked():
                    val += 1

        def writer():
            result = w1.acquire(timeout=0)
            if result:  # pragma: nocover
                vals.append(2)
            vals.append(3)
            with w1.acquire(revoke=True):
                vals.append(4)

        reader = threading.Thread(target=reader)
        writer = threading.Thread(target=writer)
        reader.start()
        ev.wait()
        eq_(vals, [1])
        writer.start()
        reader.join()
        writer.join()
        eq_(vals, [1, 3, 4])

    def testClearing(self):
        w1 = self.makeReadLock('zkLockTest')
        r1 = self.makeWriteLock('zkLockTest')

        vals = []
        ev = threading.Event()

        def reader():
            with r1.acquire():
                ev.set()
                vals.append(1)
                val = 0
                while not r1.revoked():
                    val += 1

        reader = threading.Thread(target=reader)
        reader.start()
        ev.wait()
        eq_(vals, [1])
        eq_(w1.connected, True)
        w1.clear()
        reader.join()
        eq_(vals, [1])
