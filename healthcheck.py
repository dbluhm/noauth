#!/usr/bin/env python
"""Healthcheck."""

import socket
import sys

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sys.exit(s.connect_ex(("localhost", 8080)))
