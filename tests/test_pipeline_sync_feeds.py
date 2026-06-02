"""POST /pipeline/sync-feeds — cron-protected RSS re-ingest."""

from __future__ import annotations

import pytest

from backend.api.config import get_settings
from tests.utils.db_reset import reset_v1_tables


@pytest.fixture
def v1_db_clean(v1_db_ready):
  reset_v1_tables()
  yield
  reset_v1_tables()


def test_sync_feeds_disabled_without_secret(v1_client, v1_db_clean, monkeypatch):
  monkeypatch.setenv("SOAPBOXX_CRON_SECRET", "")
  get_settings.cache_clear()
  r = v1_client.post("/pipeline/sync-feeds", headers={"X-Cron-Secret": "nope"})
  assert r.status_code == 503
  get_settings.cache_clear()


def test_sync_feeds_rejects_bad_secret(v1_client, v1_db_clean, monkeypatch):
  monkeypatch.setenv("SOAPBOXX_CRON_SECRET", "test-cron-secret")
  get_settings.cache_clear()
  r = v1_client.post("/pipeline/sync-feeds", headers={"X-Cron-Secret": "wrong"})
  assert r.status_code == 403
  get_settings.cache_clear()


def test_sync_feeds_ok_with_secret(v1_client, v1_db_clean, monkeypatch):
  monkeypatch.setenv("SOAPBOXX_CRON_SECRET", "test-cron-secret")
  get_settings.cache_clear()
  r = v1_client.post(
    "/pipeline/sync-feeds",
    headers={"X-Cron-Secret": "test-cron-secret"},
  )
  assert r.status_code == 200
  body = r.json()
  assert "podcasts_checked" in body
  assert "episodes_created" in body
  get_settings.cache_clear()
