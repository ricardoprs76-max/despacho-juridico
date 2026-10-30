from importlib import resources

from tests.api.conftest import MakeClient


def static_text(name: str) -> str:
    return (resources.files("agentes.api") / "static" / name).read_text(encoding="utf-8")


def test_root_serves_page(make_client: MakeClient) -> None:
    r = make_client([]).get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "<title>" in r.text
    assert "app.js" in r.text
    assert 'lang="es"' in r.text


def test_static_assets_served(make_client: MakeClient) -> None:
    client = make_client([])
    for path in ("/app.js", "/styles.css"):
        assert client.get(path).status_code == 200, path


def test_page_does_not_need_key(make_client: MakeClient) -> None:
    client = make_client([], api_key="s3creta")
    assert client.get("/").status_code == 200
    assert client.get("/app.js").status_code == 200


def test_api_routes_win_over_static(make_client: MakeClient) -> None:
    r = make_client([]).get("/health")
    assert r.headers["content-type"].startswith("application/json")


def test_js_never_uses_innerhtml_with_data() -> None:
    js = static_text("app.js")
    assert "innerHTML" not in js
    assert "outerHTML" not in js
    assert "insertAdjacentHTML" not in js
    assert "textContent" in js


def test_page_loads_nothing_external() -> None:
    for name in ("index.html", "app.js", "styles.css"):
        text = static_text(name)
        assert "http://" not in text and "https://" not in text, name
