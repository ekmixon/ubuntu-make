# -*- coding: utf-8 -*-
# Copyright (C) 2014 Canonical
#
# Authors:
#  Didier Roche
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""Module delivering a DownloadCenter to download in parallel multiple requests"""

import apt
import apt.progress
import apt.progress.base
from collections import namedtuple
from concurrent import futures
from contextlib import suppress
import fcntl
import logging
import os
import re
import subprocess
import tempfile
import time
from umake.tools import Singleton, add_foreign_arch, get_foreign_archs, get_current_arch, as_root

logger = logging.getLogger(__name__)


class RequirementsHandler(object, metaclass=Singleton):
    """Handle platform requirements"""

    STATUS_DOWNLOADING, STATUS_INSTALLING = range(2)

    RequirementsResult = namedtuple("RequirementsResult", ["bucket", "error"])

    def __init__(self):
        logger.info("Create a new apt cache")
        self.cache = apt.Cache()
        self.executor = futures.ThreadPoolExecutor(max_workers=1)

        # Set defaults for openjdk override
        self.jre_installed_version = None
        self.jdk_installed_version = None

    def is_bucket_installed(self, bucket):
        """Check if the bucket is installed

        The bucket is a list of packages to check if installed."""
        logger.debug(f"Check if {bucket} is installed")
        is_installed = True
        for pkg_name in bucket:
            if ' | ' in pkg_name:
                for package in pkg_name.split(' | '):
                    if self.is_bucket_installed([package]):
                        bucket.remove(pkg_name)
                        bucket.append(package)
                        pkg_name = package
                        break
            # /!\ danger: if current arch == ':appended_arch', on a non multiarch system, dpkg doesn't
            # understand that. strip :arch then
            if ":" in pkg_name:
                (pkg_without_arch_name, arch) = pkg_name.split(":", -1)
                if arch == get_current_arch():
                    pkg_name = pkg_without_arch_name
            if pkg_name not in self.cache or not self.cache[pkg_name].is_installed:
                if "openjdk" in pkg_name:
                    is_installed = self.check_java_equiv(pkg_name)
                else:
                    logger.info(f"{pkg_name} isn't installed")
                    is_installed = False
        return is_installed

    def is_bucket_available(self, bucket):
        """Check if bucket available on the platform"""
        all_in_cache = True
        for pkg_name in bucket:
            if ' | ' in pkg_name:
                for package in pkg_name.split(' | '):
                    if self.is_bucket_available([package]):
                        bucket.remove(pkg_name)
                        bucket.append(package)
                        pkg_name = package
                        break
            if pkg_name not in self.cache:
                # this can be also a foo:arch and we don't have <arch> added. Tell is may be available
                if ":" in pkg_name:
                    # /!\ danger: if current arch == ':appended_arch', on a non multiarch system, dpkg doesn't
                    # understand that. strip :arch then
                    (pkg_without_arch_name, arch) = pkg_name.split(":", -1)
                    if arch == get_current_arch() and pkg_without_arch_name in self.cache:  # false positive, available
                        continue
                    elif arch not in get_foreign_archs():  # relax the constraint
                        logger.info(
                            f"{pkg_name} isn't available on this platform, but {arch} isn't enabled. So it may be available later on"
                        )

                        continue
                if "openjdk" in pkg_name:
                    if not self.check_java_equiv(pkg_name):
                        all_in_cache = False
                else:
                    logger.info(f"{pkg_name} isn't available on this platform")
                    all_in_cache = False
        return all_in_cache

    def is_bucket_uptodate(self, bucket):
        """Check if the bucket is installed and up to date

        The bucket is a list of packages to check if installed."""
        logger.debug(f"Check if {bucket} is up to date")
        is_installed_and_uptodate = True
        for pkg_name in bucket:
            if ' | ' in pkg_name:
                for package in pkg_name.split(' | '):
                    if self.is_bucket_available([package]):
                        bucket.remove(pkg_name)
                        bucket.append(package)
                        pkg_name = package
                        break
            # /!\ danger: if current arch == ':appended_arch', on a non multiarch system, dpkg doesn't
            # understand that. strip :arch then
            if ":" in pkg_name:
                (pkg_without_arch_name, arch) = pkg_name.split(":", -1)
                if arch == get_current_arch():
                    pkg_name = pkg_without_arch_name
            if pkg_name not in self.cache or not self.cache[pkg_name].is_installed:
                logger.info(f"{pkg_name} isn't installed")
                is_installed_and_uptodate = False
            elif self.cache[pkg_name].is_upgradable:
                logger.info(f"We can update {pkg_name}")
                is_installed_and_uptodate = False
            if "openjdk" in pkg_name and self.check_java_equiv(pkg_name):
                is_installed_and_uptodate = True
        return is_installed_and_uptodate

    def check_java_equiv(self, pkg_name):
        """Add exception if java has been installed otherwhise"""
        openjdk_regex = re.search(r"openjdk-(\d+)-(j\w\w)", pkg_name)
        required_version = openjdk_regex[1]
        required_release = openjdk_regex[2]
        if required_release == "jre":
            if not self.jre_installed_version:
                try:
                    self.jre_installed_version = subprocess.check_output(["java", "-version"], stderr=subprocess.STDOUT).decode()
                except FileNotFoundError as e:
                    logger.debug("Missing java command: consider it not installed")
                    return False
            installed_version = re.search(
                r"version \"([\d\.]+).*\"", self.jre_installed_version
            )[1]

        elif required_release == "jdk":
            if not self.jdk_installed_version:
                try:
                    self.jdk_installed_version = subprocess.check_output(["javac", "-version"], stderr=subprocess.STDOUT).decode()
                except FileNotFoundError as e:
                    logger.debug("Missing javac command: consider it not installed")
                    return False
            installed_version = re.search(r"([\d\.]+).*", self.jdk_installed_version)[1]
        if installed_version >= required_version:
            logger.debug("Not installing openjdk since correct java version is already available")
            return True
        return False

    def install_bucket(self, bucket, progress_callback, installed_callback):
        """Install a specific bucket. If any other bucket is in progress, queue the request

        bucket is a list of packages to install.

        Return a tuple (num packages to install, size packages to download)"""
        logger.info(f"Installation {bucket} pending")
        bucket_pack = {
            "bucket": bucket,
            "progress_callback": progress_callback,
            "installed_callback": installed_callback
        }

        pkg_to_install = not self.is_bucket_uptodate(bucket)

        future = self.executor.submit(self._really_install_bucket, bucket_pack)
        future.tag_bucket = bucket_pack
        future.add_done_callback(self._on_done)
        return pkg_to_install

    def _really_install_bucket(self, current_bucket):
        """Really install current bucket and bind signals"""
        bucket = current_bucket["bucket"]
        logger.debug(f"Starting {bucket} installation")

        # exchange file output for apt and dpkg after the fork() call (open it empty)
        self.apt_fd = tempfile.NamedTemporaryFile(delete=False)
        self.apt_fd.close()

        if self.is_bucket_uptodate(bucket):
            return True

        need_cache_reload = False
        for pkg_name in bucket:
            if ":" in pkg_name:
                arch = pkg_name.split(":", -1)[-1]
                need_cache_reload = need_cache_reload or add_foreign_arch(arch)

        if need_cache_reload:
            with as_root():
                self._force_reload_apt_cache()
                self.cache.update()
            self._force_reload_apt_cache()

        # mark for install and so on
        for pkg_name in bucket:
            # /!\ danger: if current arch == ':appended_arch', on a non multiarch system, dpkg doesn't understand that
            # strip :arch then
            if ":" in pkg_name:
                (pkg_without_arch_name, arch) = pkg_name.split(":", -1)
                if arch == get_current_arch():
                    pkg_name = pkg_without_arch_name
            try:
                pkg = self.cache[pkg_name]
                if pkg.is_installed and pkg.is_upgradable:
                    logger.debug(f"Marking {pkg_name} for upgrade")
                    pkg.mark_upgrade()
                else:
                    logger.debug(f"Marking {pkg_name} for install")
                    pkg.mark_install(auto_fix=False)
            except Exception as msg:
                message = f"Can't mark for install {pkg_name}: {msg}"
                raise BaseException(message)

        # this can raise on installedArchives() exception if the commit() fails
        with as_root():
            self.cache.commit(fetch_progress=self._FetchProgress(current_bucket,
                                                                 self.STATUS_DOWNLOADING,
                                                                 current_bucket["progress_callback"]),
                              install_progress=self._InstallProgress(current_bucket,
                                                                     self.STATUS_INSTALLING,
                                                                     current_bucket["progress_callback"],
                                                                     self._force_reload_apt_cache,
                                                                     self.apt_fd.name))

        return True

    def _on_done(self, future):
        """Call future associated bucket done callback"""
        result = self.RequirementsResult(bucket=future.tag_bucket["bucket"], error=None)
        if future.exception():
            error_message = str(future.exception())
            with suppress(FileNotFoundError):
                with open(self.apt_fd.name) as f:
                    if subprocess_content := f.read():
                        error_message = f"{error_message}\nSubprocess output: {subprocess_content}"
            logger.error(error_message)
            result = result._replace(error=error_message)
        else:
            logger.debug(f'{future.tag_bucket["bucket"]} installed')
        os.remove(self.apt_fd.name)
        future.tag_bucket["installed_callback"](result)

    def _force_reload_apt_cache(self):
        """Loop on loading apt cache in case something else is updating"""
        try:
            self.cache.open()
        except SystemError:
            time.sleep(1)
            self._force_reload_apt_cache()

    class _FetchProgress(apt.progress.base.AcquireProgress):
        """Progress handler for downloading a bucket"""
        def __init__(self, bucket, status, progress_callback,):
            apt.progress.base.AcquireProgress.__init__(self)
            self._bucket = bucket
            self._status = status
            self._progress_callback = progress_callback

        def pulse(self, owner):
            percent = (((self.current_bytes + self.current_items) * 100.0) /
                       float(self.total_bytes + self.total_items))
            logger.debug(
                f"{self._bucket['bucket']} download update: {percent}% of {self.total_bytes}"
            )

            report = {"step": self._status, "percentage": percent, "pkg_size_download": self.total_bytes}
            self._progress_callback(report)

    class _InstallProgress(apt.progress.base.InstallProgress):
        """Progress handler for installing a bucket"""
        def __init__(self, bucket, status, progress_callback, force_load_apt_cache, exchange_filename):
            apt.progress.base.InstallProgress.__init__(self)
            self._bucket = bucket
            self._status = status
            self._progress_callback = progress_callback
            self._force_reload_apt_cache = force_load_apt_cache
            self._exchange_filename = exchange_filename

        def error(self, pkg, msg):
            logger.error(
                f"{self._bucket['bucket']} installation finished with an error: {msg}"
            )

            self._force_reload_apt_cache()  # reload apt cache
            raise BaseException(msg)

        def finish_update(self):
            # warning: this function can be called even if dpkg failed (it raised an exception around commit()
            # DO NOT CALL directly the callbacks from there.
            logger.debug(f"Install for {self._bucket['bucket']} ended.")
            self._force_reload_apt_cache()  # reload apt cache

        def status_change(self, pkg, percent, status):
            logger.debug(f"{self._bucket['bucket']} install update: {percent}")
            self._progress_callback({"step": self._status, "percentage": percent})

        @staticmethod
        def _redirect_stdin():  # pragma: no cover (in a fork)
            os.dup2(os.open(os.devnull, os.O_RDWR), 0)

        def _redirect_output(self):  # pragma: no cover (in a fork)
            fd = os.open(self._exchange_filename, os.O_RDWR)
            os.dup2(fd, 1)
            os.dup2(fd, 2)

        def _fixup_fds(self):  # pragma: no cover (in a fork)
            required_fds = [0, 1, 2,  # stdin, stdout, stderr
                            self.writefd,
                            self.write_stream.fileno(),
                            self.statusfd,
                            self.status_stream.fileno()
                            ]
            # ensure that our required fds close on exec
            for fd in required_fds[3:]:
                old_flags = fcntl.fcntl(fd, fcntl.F_GETFD)
                fcntl.fcntl(fd, fcntl.F_SETFD, old_flags | fcntl.FD_CLOEXEC)
            # close all fds
            proc_fd = "/proc/self/fd"
            if os.path.exists(proc_fd):
                error_count = 0
                for fdname in os.listdir(proc_fd):
                    try:
                        fd = int(fdname)
                    except ValueError:
                        print("ERROR: can not get fd for '%s'" % fdname)
                    if fd in required_fds:
                        continue
                    try:
                        os.close(fd)
                    except OSError as e:
                        # there will be one fd that can not be closed
                        # as its the fd from pythons internal diropen()
                        # so its ok to ignore one close error
                        error_count += 1
                        if error_count > 1:
                            print(f"ERROR: os.close({fd}): {e}")

        def fork(self):
            pid = os.fork()
            if pid == 0:  # pragma: no cover
                # be root
                os.seteuid(0)
                os.setegid(0)
                self._fixup_fds()
                self._redirect_stdin()
                self._redirect_output()
            return pid
