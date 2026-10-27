#!/usr/bin/env python3
from scripts.browser_session_lib import open_logged_in_session

session = open_logged_in_session(source='hiring_post_monitor')
print('Mode:', session.mode)
print('URL:', session.page.url)
print('Auth state:', session.check_auth_state())
session.close()