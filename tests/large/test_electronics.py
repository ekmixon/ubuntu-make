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

"""Tests for the IDE category"""
import logging
import platform
import subprocess
import os
from tests.large import LargeFrameworkTests
from tests.tools import UMAKE, spawn_process

logger = logging.getLogger(__name__)


class ArduinoIDETests(LargeFrameworkTests):
    """The Arduino Software distribution from the IDE collection."""

    TIMEOUT_INSTALL_PROGRESS = 120
    TIMEOUT_START = 60
    TIMEOUT_STOP = 60

    def setUp(self):
        super().setUp()
        self.installed_path = os.path.join(self.install_base_path, "electronics", "arduino")
        self.desktop_filename = "arduino.desktop"

    @property
    def arch_option(self):
        """we return the expected arch call on command line"""
        return platform.machine()

    def test_default_install(self):
        """Install Arduino from scratch test case"""
        self.child = spawn_process(self.command(f'{UMAKE} electronics arduino'))
        self.expect_and_no_warn(f"Choose installation path: {self.installed_path}")
        self.child.sendline("")
        self.expect_and_no_warn(r"Installation done", timeout=self.TIMEOUT_INSTALL_PROGRESS)
        self.wait_and_close()

        # we have an installed launcher, added to the launcher and an icon file
        self.assertTrue(self.launcher_exists_and_is_pinned(self.desktop_filename))
        self.assert_exec_exists()
        self.assert_icon_exists()
        self.assertTrue(self.is_in_group("dialout"))
        self.assert_exec_link_exists()

        # launch it, send SIGTERM and check that it exits fine
        proc = subprocess.Popen(self.command_as_list(self.exec_path), stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)

        self.check_and_kill_process(["java", "processing.app.Base"], wait_before=self.TIMEOUT_START)
        proc.communicate()
        proc.wait(self.TIMEOUT_STOP)

        # ensure that it's detected as installed:
        self.child = spawn_process(self.command(f'{UMAKE} electronics arduino'))
        self.expect_and_no_warn(r"Arduino is already installed.*\[.*\] ")
        self.child.sendline()
        self.wait_and_close()


class EagleTests(LargeFrameworkTests):
    """The Eagle Autodesk tests."""

    TIMEOUT_INSTALL_PROGRESS = 120
    TIMEOUT_START = 60
    TIMEOUT_STOP = 60

    def setUp(self):
        super().setUp()
        self.installed_path = os.path.join(self.install_base_path, "electronics", "eagle")
        self.desktop_filename = "eagle.desktop"
        self.command_args = f'{UMAKE} electronics eagle'
        self.name = "Eagle"

    def test_default_eclipse_ide_install(self):
        """Install eclipse from scratch test case"""
        self.child = spawn_process(self.command(self.command_args))
        self.expect_and_no_warn(f"Choose installation path: {self.installed_path}")
        self.child.sendline("")
        self.expect_and_no_warn(r"Installation done", timeout=self.TIMEOUT_INSTALL_PROGRESS)
        self.wait_and_close()

        # we have an installed launcher, added to the launcher and an icon file
        self.assertTrue(self.launcher_exists_and_is_pinned(self.desktop_filename))
        self.assert_exec_exists()
        self.assert_icon_exists()
        self.assert_exec_link_exists()

        # launch it, send SIGTERM and check that it exits fine
        proc = subprocess.Popen(self.command_as_list(self.exec_path), stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, preexec_fn=os.setsid)

        self.check_and_kill_process(proc,
                                    wait_before=self.TIMEOUT_START, send_sigkill=True)
        proc.communicate()
        proc.wait(self.TIMEOUT_STOP)

        # ensure that it's detected as installed:
        self.child = spawn_process(self.command(self.command_args))
        self.expect_and_no_warn(f"{self.name} is already installed.*\[.*\] ")
        self.child.sendline()
        self.wait_and_close()


class FritzingTests(LargeFrameworkTests):
    """The Eagle Autodesk tests."""

    TIMEOUT_INSTALL_PROGRESS = 120
    TIMEOUT_START = 60
    TIMEOUT_STOP = 60

    def setUp(self):
        super().setUp()
        self.installed_path = os.path.join(self.install_base_path, "electronics", "fritzing")
        self.desktop_filename = "fritzing.desktop"
        self.command_args = f'{UMAKE} electronics fritzing'
        self.name = "Fritzing"

    def test_default_eclipse_ide_install(self):
        """Install fritzing from scratch test case"""
        self.child = spawn_process(self.command(self.command_args))
        self.expect_and_no_warn(f"Choose installation path: {self.installed_path}")
        self.child.sendline("")
        self.expect_and_no_warn("Installation done", timeout=self.TIMEOUT_INSTALL_PROGRESS)
        self.wait_and_close()

        # we have an installed launcher, added to the launcher and an icon file
        self.assertTrue(self.launcher_exists_and_is_pinned(self.desktop_filename))
        self.assert_exec_exists()
        self.assert_icon_exists()
        self.assert_exec_link_exists()

        # launch it, send SIGTERM and check that it exits fine
        proc = subprocess.Popen(self.command_as_list(self.exec_path), stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)

        self.check_and_kill_process([self.installed_path, "lib/Fritzing"], wait_before=self.TIMEOUT_START)
        proc.wait(self.TIMEOUT_STOP)

        # ensure that it's detected as installed:
        self.child = spawn_process(self.command(self.command_args))
        self.expect_and_no_warn(f"{self.name} is already installed.*\[.*\] ")
        self.child.sendline()
        self.wait_and_close()
