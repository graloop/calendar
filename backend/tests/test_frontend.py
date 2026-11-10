# The page itself: that it's served at its addresses, that nothing is left
# untranslated (the French list is easy to forget, so a test keeps it honest),
# and the house rules: text never goes in as HTML, no pop-ups, colours only
# from the shared settings so night mode reaches everything.

import pathlib
import re
from html.parser import HTMLParser

from app.version import VERSION

ROOT = pathlib.Path(__file__).parent.parent
FRONTEND = ROOT / "frontend"
FR_SOURCE = (FRONTEND / "js/core/fr.js").read_text(encoding="utf-8")
JS_FILES = [p for p in (FRONTEND / "js").rglob("*.js") if p.name != "fr.js"]
JS_SOURCE = "\n".join(p.read_text(encoding="utf-8") for p in JS_FILES)
# Same in both languages, or not language at all.
NOT_TRANSLATED = {"Agenda", "graloop", "gral", "p", "English", "Français", "Agenda v__APP_VERSION__"}


def french_has(text: str) -> bool:
    bare = text.replace("\\", "")
    keys = re.findall(r'^\s*(?:"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'|(\w+)):', FR_SOURCE, re.M)
    return any(bare == (a or b or c).replace("\\", "") for a, b, c in keys)


class VisibleText(HTMLParser):
    SKIPPED = {"script", "style", "svg"}

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.found = set()

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIPPED:
            self.depth += 1
        for name, value in attrs:
            if name in ("placeholder", "aria-label", "title", "alt") and value:
                self.found.add(value)

    def handle_endtag(self, tag):
        if tag in self.SKIPPED:
            self.depth -= 1

    def handle_data(self, data):
        text = " ".join(data.split())
        if text and not self.depth:
            self.found.add(text)


def test_every_index_html_text_has_french():
    parser = VisibleText()
    parser.feed((FRONTEND / "index.html").read_text(encoding="utf-8"))
    missing = {text for text in parser.found - NOT_TRANSLATED if not french_has(text)}
    assert not missing


def test_every_script_string_has_french():
    strings = re.findall(r"\bt\(\s*(?:\"((?:[^\"\\]|\\.)*)\"|'((?:[^'\\]|\\.)*)')", JS_SOURCE)
    assert strings
    missing = {a or b for a, b in strings if not french_has(a or b)}
    assert not missing


def test_every_event_type_has_french():
    labels = re.search(r"const LABELS = \{(.*?)\};", (FRONTEND / "js/core/types.js").read_text(), re.S).group(1)
    words = re.findall(r':\s*"([^"]+)"', labels)
    assert len(words) == 8
    assert all(french_has(w) for w in words)


def test_every_server_message_has_french():
    source = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "app").rglob("*.py"))
    messages = re.findall(r'HTTP_\w+, "([^"]+)"\)', source)
    messages += re.findall(r'ValueError\("([^"]+)"\)', source)
    assert len(messages) > 5
    missing = {m for m in messages if not french_has(m)}
    assert not missing


def test_every_import_line_message_has_french():
    # The preview shows these next to a line, translated by their template.
    source = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "app/importing").glob("*.py"))
    templates = re.findall(r'LineError\(\s*"((?:[^"\\]|\\.)*)"', source)
    assert len(templates) > 15
    missing = {m for m in templates if not french_has(m)}
    assert not missing


def test_index_is_served_with_versioned_assets(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "<title>Agenda</title>" in response.text
    assert re.search(r'src="/js/main\.js\?v=\d+"', response.text)
    assert re.search(r'href="/css/base\.css\?v=\d+"', response.text)


def test_every_page_address_opens_the_same_page(client):
    home = client.get("/").text
    for path in ("/upcoming", "/week", "/week/2026-11-23", "/month", "/month/2026-11", "/event/5", "/event/new", "/import"):
        assert client.get(path).text == home, path


def test_the_graloop_logo_is_at_the_top(client):
    html = client.get("/").text
    assert '<span class="logo" role="img" aria-label="graloop">gral<svg' in html
    assert html.index('class="logo"') < html.index("<main>")


def test_scripts_and_styles_are_served(client):
    for path in ("/js/main.js", "/css/base.css", "/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon.svg"):
        assert client.get(path).status_code == 200, path


def test_every_module_a_script_imports_exists():
    for script in JS_FILES:
        for target in re.findall(r'(?:from |import )"(\.[^"]+)"', script.read_text(encoding="utf-8")):
            assert (script.parent / target).resolve().exists(), f"{script.name} -> {target}"


def test_scripts_never_build_html_from_strings():
    # An event's text may come from an email or Moodle: it must only ever go in as text.
    assert "innerHTML" not in JS_SOURCE
    assert "outerHTML" not in JS_SOURCE
    assert "insertAdjacentHTML" not in JS_SOURCE


def test_no_browser_pop_ups():
    # A browser pop-up would stop the Claude extension, which can't answer one.
    for word in ("confirm(", "alert(", "prompt("):
        assert word not in JS_SOURCE, word


CSS_FILES = sorted((FRONTEND / "css").glob("*.css"))
BASE_CSS = (FRONTEND / "css/base.css").read_text(encoding="utf-8")


def _tokens(block_start: str) -> set[str]:
    block = BASE_CSS.split(block_start, 1)[1].split("}", 1)[0]
    return set(re.findall(r"(--[\w-]+):", block))


def test_day_colours_are_the_planned_ones():
    day = BASE_CSS.split(":root {", 1)[1].split("}", 1)[0]
    for setting in ("--bg: #fbf8f5", "--accent: #ea580c", "--nav-bg: #431407", "--changed: #e0f2fe"):
        assert setting in day


def test_night_mode_sets_every_colour_the_day_sets():
    day, night = _tokens(":root {"), _tokens(':root[data-theme="dark"] {')
    assert len(day) > 15
    assert day == night


def test_screen_styles_only_use_the_colour_settings():
    # A colour written straight into these files would stay the same at night.
    # White text on an orange button reads well in both.
    for path in CSS_FILES:
        if path.name == "base.css":
            continue
        colours = set(re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)", path.read_text(encoding="utf-8")))
        assert colours <= {"#fff"}, (path.name, colours)


def test_night_mode_is_set_before_the_page_is_drawn(client):
    html = client.get("/").text
    head = html.split("</head>", 1)[0]
    assert "ag_theme" in head
    assert head.index("dataset.theme") < head.index("stylesheet")
    assert 'id="theme-switch"' in html and 'role="switch"' in html


def test_api_docs_are_off_by_default(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_version_shows_in_settings(client):
    assert f"Agenda v{VERSION}<" in client.get("/").text


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}
