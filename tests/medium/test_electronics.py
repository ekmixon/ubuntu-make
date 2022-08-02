# -*- coding: utf-8 -*-
# Copyright (C) 2014 Canonical
#
# Authors:
#  Didier Roche
#  Tin Tvrtković
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

"""Tests for ides"""

from . import ContainerTests
import os

from ..large import test_electronics
from ..tools import get_data_dir, swap_file_and_restore, UMAKE


class ArduinoIDEInContainer(ContainerTests, test_electronics.ArduinoIDETests):
    """This will test the Arduino IDE integration inside a container"""

    TIMEOUT_START = 20
    TIMEOUT_STOP = 10

    def setUp(self):
        self.hosts = {443: ["www.arduino.cc", "downloads.arduino.cc"]}
        self.apt_repo_override_path = os.path.join(self.APT_FAKE_REPO_PATH, 'arduino')
        super().setUp()
        # override with container path
        self.installed_path = os.path.join(self.install_base_path, "electronics", "arduino")

    def test_install_with_changed_download_page(self):
        """Installing arduino ide should fail if download page has significantly changed"""
        download_page_file_path = os.path.join(get_data_dir(), "server-content", "www.arduino.cc", "en", "Main",
                                               "Software")
        umake_command = self.command(f'{UMAKE} electronics arduino')
        self.bad_download_page_test(umake_command, download_page_file_path)
        self.assertFalse(self.launcher_exists_and_is_pinned(self.desktop_filename))
        self.assertFalse(self.is_in_path(self.exec_link))

    def test_install_with_changed_checksum_page(self):
        """Installing arduino ide should fail if checksum link is unparsable"""
        download_page_file_path = os.path.join(get_data_dir(), "server-content", "downloads.arduino.cc",
                                               "arduino-mock.sha512sum.txt")
        umake_command = self.command(f'{UMAKE} electronics arduino')
        self.bad_download_page_test(umake_command, download_page_file_path)
        self.assertFalse(self.launcher_exists_and_is_pinned(self.desktop_filename))
        self.assertFalse(self.is_in_path(self.exec_link))


class EagleTestsInContainer(ContainerTests, test_electronics.EagleTests):
    """This will test the Eagle integration inside a container"""

    TIMEOUT_START = 20
    TIMEOUT_STOP = 10

    def setUp(self):
        self.hosts = {443: ["eagle-updates.circuits.io"]}
        super().setUp()
        # override with container path
        self.installed_path = os.path.join(self.install_base_path, "electronics", "eagle")

    def test_install_with_changed_download_page(self):
        """Installing eagle ide should fail if download page has significantly changed"""
        download_page_file_path = os.path.join(get_data_dir(), "server-content", "eagle-updates.circuits.io",
                                               "downloads", "latest.html")
        umake_command = self.command(f'{UMAKE} electronics eagle')
        self.bad_download_page_test(umake_command, download_page_file_path)
        self.assertFalse(self.launcher_exists_and_is_pinned(self.desktop_filename))
        self.assertFalse(self.is_in_path(self.exec_link))


class FritzingInContainer(ContainerTests, test_electronics.FritzingTests):
    """This will test the Fritzing integration inside a container"""

    TIMEOUT_START = 20
    TIMEOUT_STOP = 10

    def setUp(self):
        self.hosts = {443: ["api.github.com", "github.com"]}
        self.apt_repo_override_path = os.path.join(self.APT_FAKE_REPO_PATH, 'fritzing')
        super().setUp()
        # override with container path
        self.installed_path = os.path.join(self.install_base_path, "electronics", "fritzing")

    def test_install_with_changed_download_page(self):
        """Installing Fritzing should fail if download page has significantly changed"""
        download_page_file_path = os.path.join(get_data_dir(), "server-content", "api.github.com",
                                               "repos", "Fritzing", "Fritzing-app", "releases", "latest")
        umake_command = self.command(f'{UMAKE} electronics Fritzing')
        self.bad_download_page_test(self.command(self.command_args), download_page_file_path)
        self.assertFalse(self.launcher_exists_and_is_pinned(self.desktop_filename))
        self.assertFalse(self.is_in_path(self.exec_link))

    def test_install_beta_with_changed_download_page(self):
        """Installing Fritzing Beta should fail if the latest is not a edge"""
        download_page_file_path = os.path.join(get_data_dir(), "server-content", "api.github.com",
                                               "repos", "Fritzing", "Fritzing-app", "releases", "index.html")
        with swap_file_and_restore(download_page_file_path) as content:
            with open(download_page_file_path, "w") as newfile:
                newfile.write(content.replace("-edge", ""))
            self.child = umake_command = self.command(f'{UMAKE} ide fritzing --edge')
            self.assertFalse(self.launcher_exists_and_is_pinned(self.desktop_filename))
            self.assertFalse(self.is_in_path(self.exec_link))
