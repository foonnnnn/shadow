import unittest
import sys
import os
sys.path.insert(0, os.path.dirname('../'))
from shadow import Shadow
import tempfile
import shutil
import string
from random import Random
from subprocess import Popen

class ShadowTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.kernel_dir = os.path.join(self.tmp_dir, 'boot')
        self.rootfs_dir = os.path.join(self.tmp_dir, 'rootfs')
        self.snap_dir = os.path.join(self.tmp_dir, 'shadow')
        self.shadow = Shadow(rootfs_dir=self.rootfs_dir, kernel_dir=self.kernel_dir, snap_dir=self.snap_dir)
        self.timestamp = self.shadow._get_timestamp()
        os.makedirs(self.kernel_dir)
        os.makedirs(self.rootfs_dir)
        os.makedirs(self.snap_dir)
        # preload some test "kernels" and "ramdisks"
        for x in ['kernel26.img', 'vmlinuz26', 'initrd.img-2.6.38', 'vmlinuz.2.6.38']:
            f = open(os.path.join(self.kernel_dir, x), 'w')
            f.write(x)
            f.close()
        for x in range(10):
            r_dir = ''.join(Random().sample(string.letters, 8))
            os.makedirs(os.path.join(self.rootfs_dir, r_dir))
    
    def test_snapshot_kernels(self):
        self.shadow._snap_kernels()
        self.assertNotEqual(len(os.listdir(self.kernel_dir)), 0)

    @unittest.skipIf(os.geteuid() != 0, "You must be root to test btrfs snapshots")
    def test_snapshot_rootfs(self):
        # remove rootfs dir or btrfs subvolume create will fail
        if os.path.exists(self.rootfs_dir):
            shutil.rmtree(self.rootfs_dir)
        # create the test subvolume
        p = Popen(['btrfs subvolume create {0} 2>&1 > /dev/null'.format(self.rootfs_dir)], shell=True)
        p.wait()
        # snapshot
        self.shadow._snap_rootfs()
        self.assertNotEqual(len(self.shadow.get_snapshots()), 0)
        self.shadow.clear_snapshots()
        self.assertEqual(len(self.shadow.get_snapshots()), 0)
        # remove test subvolume
        p = Popen(['btrfs subvolume delete {0} 2>&1 > /dev/null'.format(self.rootfs_dir)], shell=True)
        p.wait()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

if __name__=='__main__':
    unittest.main()
