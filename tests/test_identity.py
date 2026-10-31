"""Identity-only packaging regression checks. Run with unittest + PyYAML."""
import json
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


def manifest():
    return yaml.safe_load((ROOT / "wizard.md").read_text().split("---", 2)[1])


class IdentityTests(unittest.TestCase):
    def test_app_id_matches_display_name_and_keeps_migration_source(self):
        doc = manifest()
        self.assertEqual(doc["id"], NEW_ID)
        self.assertEqual(doc["renamed_from"], [OLD_ID])
        self.assertEqual(doc["name"].lower().replace(" ", "-"), NEW_ID)

    def test_packaging_identity_and_version_agree(self):
        doc = manifest()
        cfg = json.loads((ROOT / "runtipi/config.json").read_text())
        self.assertEqual(cfg["id"], doc["id"])
        self.assertEqual(cfg["name"], doc["name"])
        self.assertEqual(cfg["version"], doc["version"])
        self.assertEqual(doc["version"], VERSION)
        compose = yaml.safe_load((ROOT / "runtipi/docker-compose.yml").read_text())
        self.assertIn(NEW_ID, compose["services"])
        self.assertNotIn(OLD_ID, compose["services"])

import asyncio
import os
import subprocess
import sys
import types
from unittest.mock import patch

NEW_ID = "home-assistant"
OLD_ID = "smart-home"
VERSION = "0.2.3"


def front_module():
    module = types.ModuleType("identity_front")
    with patch.dict(os.environ, {"WIZARD_APP": NEW_ID, "APP_VERSION": VERSION}):
        for name in ("front.py", "tools.py"):
            path = ROOT / "mcp" / name
            exec(compile(path.read_text(), str(path), "exec"), module.__dict__)
    return module


class CompatibilityTests(unittest.TestCase):
    def test_volume_oauth_and_dns_aliases_survive_rename(self):
        compose = yaml.safe_load((ROOT / "runtipi/docker-compose.yml").read_text())
        self.assertEqual(compose["volumes"]["home-assistant-config"]["name"], "wizard-smart-home-config")
        svc = compose["services"][NEW_ID]
        engine = compose["services"]["home-assistant-engine"]
        self.assertIn("home-assistant-config:/ha", svc["volumes"])
        self.assertIn("home-assistant-config:/config", engine["volumes"])
        self.assertIn(OLD_ID, svc["networks"]["default"]["aliases"])
        self.assertIn("smart-home-engine", engine["networks"]["default"]["aliases"])
        self.assertEqual(svc["environment"]["UPSTREAM_HOST"], "home-assistant-engine")
        self.assertEqual(svc["environment"]["WIZARD_APP"], NEW_ID)
        self.assertEqual(svc["environment"]["APP_VERSION"], VERSION)
        self.assertEqual(front_module().CLIENT_ID, "http://smart-home/")
        self.assertEqual(manifest()["provides"], ["smart-home"])

    def test_canonical_routes_and_skill(self):
        self.assertEqual(manifest()["view"]["path"], "/home-assistant/")
        self.assertEqual(manifest()["health"], "/home-assistant/healthz")
        skill = yaml.safe_load((ROOT / "SKILL.md").read_text().split("---", 2)[1])
        self.assertEqual(skill["name"], NEW_ID)

    def test_generated_compose_is_current(self):
        run = subprocess.run([sys.executable, "mcp/inline.py", "--check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)


class LocalHTTPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = front_module()
        self.app.__dict__["_ha_up"] = lambda: []  # no real Home Assistant/device calls
        self.server = await asyncio.start_server(self.app.handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def request(self, path, body=None):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        payload = b"" if body is None else json.dumps(body).encode()
        method = "GET" if body is None else "POST"
        writer.write((f"{method} {path} HTTP/1.1\r\nHost: localhost\r\nContent-Length: {len(payload)}\r\n\r\n").encode() + payload)
        await writer.drain()
        response = await reader.read()
        writer.close()
        await writer.wait_closed()
        head, _, data = response.partition(b"\r\n\r\n")
        self.assertTrue(head.startswith(b"HTTP/1.1 200"), head)
        return data

    async def test_both_paths_serve_page_assets_and_health(self):
        for suffix in ("", "index.html", "app.js", "app.css", "healthz"):
            with self.subTest(suffix=suffix):
                canonical = await self.request("/home-assistant/" + suffix)
                legacy = await self.request("/smart-home/" + suffix)
                self.assertEqual(canonical, legacy)
        health = json.loads(await self.request("/home-assistant/healthz"))
        self.assertEqual(health["app"], NEW_ID)
        self.assertEqual(health["version"], VERSION)
        self.assertIn(b'data-app="home-assistant"', await self.request("/home-assistant/"))

    async def test_mcp_identity_changes_but_tool_names_do_not(self):
        result = json.loads(await self.request("/mcp", {"jsonrpc": "2.0", "id": 1, "method": "initialize"}))
        self.assertEqual(result["result"]["serverInfo"], {"name": NEW_ID, "version": VERSION})
        result = json.loads(await self.request("/mcp", {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}))
        self.assertEqual({tool["name"] for tool in result["result"]["tools"]},
                         {"home_status", "home_devices", "home_device", "home_camera", "home_control"})
