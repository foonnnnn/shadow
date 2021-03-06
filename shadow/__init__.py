#!/usr/bin/env python
#
#

import os
import subprocess
from datetime import date, datetime
import shutil
import logging
import commands

def find_os_version():
    os_ver = platform.linux_distribution()
    if os_ver[0] != '':
        return os_ver
    if os.path.exists('/etc/arch-release'):
        kernel_ver = platform.uname()[2]
        return ('ArchLinux', kernel_ver, '')

class Shadow(object):
    def __init__(self, rootfs_dir='/', kernel_dir='/boot', snapshot_dir='/.shadow', debug=False):
        self.log = logging.getLogger('shadow')
        self._kernel_dir = kernel_dir
        self._rootfs_dir = rootfs_dir
        self._snap_dir = snapshot_dir
        self._snapshots = None
        if debug:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
        if not os.path.exists(self._snap_dir):
            os.makedirs(self._snap_dir)
        # gather snapshots
        self._gather_snapshots()

    def get_snapshots(self):
        self.log.debug('Getting snapshots from {0}'.format(self._snap_dir))
        return self._gather_snapshots()
        
    def _check_root_filesystem(self):
        """
        Checks root filesystem for compatibility

        :rtype boolean:

        """
        mounts = commands.getoutput('mount').split('\n')
        for m in mounts:
            if m.find(' / ') > -1:
                root_fs = m
        if root_fs.find('btrfs') > -1:
            self.log.debug('Found btrfs filesystem on {0}'.format(root_fs))
            return True
        else:
            self.log.error('Only root filesystems on btrfs are supported')
            return False

    def _gather_snapshots(self):
        if os.path.exists(self._snap_dir):
            self._snapshots = os.listdir(self._snap_dir)
        return self._snapshots

    @staticmethod
    def _get_timestamp():
        return datetime.strftime(datetime.now(), '%Y%m%d%H%M')

    def clear_snapshots(self):
        for s in self._snapshots:
            self.log.debug('Removing snapshot {0} from {1}'.format(s, self._snap_dir))
            p = subprocess.Popen(['btrfs subvolume delete {0} 2>&1 > /dev/null'.format(os.path.join(self._snap_dir, s))], shell=True)
            p.wait()
            self.log.debug('Removing kernel/initrd snapshot for {0}'.format(s))
            p = subprocess.Popen(['find {0} -name "*{1}" -delete'.format(self._kernel_dir, s)], shell=True)
            p.wait()
        self._gather_snapshots()
        self.log.info('Snapshots cleared')

    def remove_snapshot(self, snapshot_id=None):
        """
        Removes specified snapshot

        """
        if os.path.exists(os.path.join(self._snap_dir, snapshot_id)):
            self.log.info('Removing snapshot {0} from {1}'.format(snapshot_id, self._snap_dir))
            p = subprocess.Popen(['btrfs subvolume delete {0} 2>&1 > /dev/null'.format(os.path.join(self._snap_dir, snapshot_id))], shell=True)
            p.wait()
        kernel_found = False
        for k in os.listdir(self._kernel_dir):
            if snapshot_id in k:
                kernel_found = True
                break
        if kernel_found:
            self.log.info('Removing kernel/initrd snapshot for {0}'.format(snapshot_id))
            p = subprocess.Popen(['find {0} -name "*{1}" -delete'.format(self._kernel_dir, snapshot_id)], shell=True)
            p.wait()

    def activate_snapshot(self, snapshot_id=None):
        """
        Activates a snapshot for next boot

        """
        if os.path.exists(os.path.join(self._snap_dir, snapshot_id)):
            self.log.info('Activating snapshot {0} from {1}'.format(snapshot_id, self._snap_dir))
            p = subprocess.Popen(['btrfs subvolume set-default {0} {1} 2>&1 > /dev/null'.format(os.path.join(self._snap_dir, snapshot_id), self._rootfs_dir)], shell=True)
            p.wait()
        kernel_found = False
        for k in os.listdir(self._kernel_dir):
            if snapshot_id in k:
                kernel_found = True
                break
        if kernel_found:
            self.log.info('Activating kernel/initrd snapshot for {0}'.format(snapshot_id))
            for f in os.listdir(self._kernel_dir):
                if f.find(snapshot_id) > -1:
                    shutil.move(os.path.join(self._kernel_dir, f), os.path.join(self._kernel_dir, '{0}'.format(f.replace('.{0}'.format(snapshot_id), ''))))

    def _snap_kernels(self, timestamp=None):
        """
        Takes a snapshot of the system kernels and ramdisks

        """
        if not timestamp:
            timestamp = self._get_timestamp()
        for k in os.listdir(self._kernel_dir):
            # find kernels
            if k.find('kernel') > -1 or k.find('vmlinuz') > -1 or k.find('initrd') > -1:
                self.log.debug('Creating snapshot for kernel or initrd: {0}.{1}'.format(k, timestamp))
                shutil.copy(os.path.join(self._kernel_dir, k), os.path.join(self._kernel_dir, '{0}.{1}'.format(k, timestamp)))

    def _snap_rootfs(self, timestamp=None):
        """
        Takes a snapshot of the root filesystem (if supported)

        """
        if not timestamp:
            timestamp = self._get_timestamp()
        if self._check_root_filesystem():
            cmd = 'btrfs subvolume snapshot {0} {1}/{2} 2>&1 > /dev/null'.format(self._rootfs_dir, self._snap_dir, timestamp)
            p = subprocess.Popen([cmd], shell=True)
            ret_code = p.wait()
            if ret_code != 0:
                self.log.error('Error creating root fs snapshot.  Check syslog')
            else:
                self.log.debug('Creating snapshot for root fs: {0}'.format(timestamp))

    def take_snapshot(self, timestamp=None):
        """
        Takes a system snapshot (kernels and root fs)

        """
        if not timestamp:
            timestamp = self._get_timestamp()
        # snapshot kernels/initrds
        self._snap_kernels(timestamp=timestamp)
        # snapshot root fs (/)
        self._snap_rootfs(timestamp=timestamp)
        # reload snapshots
        self._gather_snapshots()
        self.log.info('Created snapshot {0}'.format(timestamp))
        return timestamp

