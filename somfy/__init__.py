"""Somfy RS-485 SDN Interface"""
from somfy.payloads import register_documented_payloads

# Make sure we register the payloads for typesafe parsing
register_documented_payloads()
