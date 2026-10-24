import json


def test_pwa_manifest_is_served_from_application_root(client):
    response = client.get("/manifest.webmanifest")

    assert response.status_code == 200
    assert response.mimetype == "application/manifest+json"
    manifest = json.loads(response.get_data(as_text=True))
    assert manifest["start_url"] == "/"
    assert manifest["scope"] == "/"
    assert manifest["display"] == "standalone"
    assert manifest["icons"][0]["src"].endswith("leaf-icon.svg")


def test_service_worker_has_root_scope_and_only_uses_offline_shell(client):
    response = client.get("/service-worker.js")
    script = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.headers["Service-Worker-Allowed"] == "/"
    assert '"/static/offline.html"' in script
    assert "request.mode === \"navigate\"" in script


def test_base_page_links_manifest_and_registers_service_worker(client):
    response = client.get("/")
    script_response = client.get("/static/js/main.js")

    assert response.status_code == 200
    assert b"/manifest.webmanifest" in response.data
    assert b"main.js" in response.data
    assert b"/service-worker.js" in script_response.data