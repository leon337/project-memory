from __future__ import annotations

from collections.abc import Iterator

import pytest

from context_anchor.actions import ActionExecutor


@pytest.fixture
def executor() -> Iterator[ActionExecutor]:
    active = ActionExecutor(headless=True)
    active.start()
    try:
        yield active
    finally:
        active.close()


SEARCH_FIXTURES = [
    pytest.param(
        """
        <base href="https://www.google.com/">
        <title>inteligência artificial - Google Search</title>
        <header><nav><a href="/search?tbm=isch">Imagens</a></nav></header>
        <div id="search">
          <div data-text-ad>
            <a href="https://ads.example/sale"><h3>Resultado patrocinado</h3></a>
          </div>
          <div class="g">
            <a href="/url?q=https%3A%2F%2Fexample.org%2Fgoogle-first&amp;sa=U">
              <h3>Primeiro resultado Google</h3>
            </a>
            <p>Um trecho orgânico útil.</p>
          </div>
          <div class="g">
            <a href="https://example.org/google-second"><h3>Segundo resultado Google</h3></a>
          </div>
        </div>
        """,
        "Primeiro resultado Google",
        "https://example.org/google-first",
        id="google",
    ),
    pytest.param(
        """
        <base href="https://duckduckgo.com/">
        <title>josiel at DuckDuckGo</title>
        <nav><a href="/?ia=images">Images</a></nav>
        <div class="results">
          <article class="result result--ad">
            <h2><a class="result__a" href="https://ads.example/ddg">Sponsored entry</a></h2>
          </article>
          <article class="result" data-testid="result">
            <h2>
              <a data-testid="result-title-a"
                 href="/l/?uddg=https%3A%2F%2Fexample.org%2Fduck-first">
                Significado do nome Josiel
              </a>
            </h2>
            <p>Origem e significado.</p>
          </article>
          <article class="result" data-testid="result">
            <h2><a data-testid="result-title-a" href="https://example.org/duck-second">Outro resultado</a></h2>
          </article>
        </div>
        """,
        "Significado do nome Josiel",
        "https://example.org/duck-first",
        id="duckduckgo",
    ),
    pytest.param(
        """
        <base href="https://www.bing.com/">
        <title>clima - Search</title>
        <nav><a href="/images/search?q=clima">Images</a></nav>
        <main>
          <ol id="b_results">
            <li class="b_ad"><h2><a href="https://ads.example/bing">Ad listing</a></h2></li>
            <li class="b_algo">
              <h2><a href="https://example.org/bing-first">Previsão confiável</a></h2>
              <p>Dados meteorológicos.</p>
            </li>
            <li class="b_algo"><h2><a href="https://example.org/bing-second">Outra previsão</a></h2></li>
          </ol>
        </main>
        """,
        "Previsão confiável",
        "https://example.org/bing-first",
        id="bing",
    ),
    pytest.param(
        """
        <title>Busca do portal</title>
        <header><a href="https://example.org/login">Entrar</a></header>
        <main>
          <h1>Resultados</h1>
          <article class="search-result">
            <h2><a href="https://example.org/generic-first">Resultado genérico principal</a></h2>
            <p>Conteúdo principal com    espaços e\nquebras.</p>
          </article>
          <article class="search-result">
            <h2><a href="https://example.org/generic-second">Resultado genérico secundário</a></h2>
          </article>
        </main>
        """,
        "Resultado genérico principal",
        "https://example.org/generic-first",
        id="generic",
    ),
]


@pytest.mark.parametrize(("html", "expected_title", "expected_url"), SEARCH_FIXTURES)
def test_observe_browser_extracts_first_organic_result_from_fixture(
    executor: ActionExecutor,
    html: str,
    expected_title: str,
    expected_url: str,
) -> None:
    assert executor._page is not None
    executor._page.set_content(html, wait_until="domcontentloaded")

    snapshot = executor.observe_browser()

    assert snapshot["first_result"] == {"title": expected_title, "url": expected_url}
    assert snapshot["first_result_title"] == expected_title
    assert snapshot["first_result_url"] == expected_url
    assert snapshot["search_results"][0] == snapshot["first_result"]
    assert all("ads.example" not in item["url"] for item in snapshot["search_results"])
    assert all("ads.example" not in item["url"] for item in snapshot["links"])
    assert all("patrocinado" not in item["text"].casefold() for item in snapshot["headings"])


def test_observe_browser_returns_compact_current_page_snapshot(executor: ActionExecutor) -> None:
    assert executor._page is not None
    executor._page.set_content(
        """
        <title>  Página   atual </title>
        <nav><h2>Navegação descartada</h2><a href="https://example.org/images">Imagens</a></nav>
        <main>
          <h1>Estado observado</h1>
          <p>Texto      útil\n\ncompactado.</p>
          <a href="https://example.org/detail">Leia os detalhes</a>
        </main>
        """,
        wait_until="domcontentloaded",
    )

    snapshot = executor.observe_browser(max_text_chars=32)

    assert snapshot["source"] == "browser"
    assert snapshot["observation_method"] == "playwright_dom"
    assert snapshot["url"] == "about:blank"
    assert snapshot["title"] == "Página atual"
    assert snapshot["http_status"] is None
    assert snapshot["text"] == "Estado observado Texto útil comp"
    assert snapshot["headings"] == [{"level": 1, "text": "Estado observado"}]
    assert snapshot["links"] == [
        {"text": "Leia os detalhes", "url": "https://example.org/detail"}
    ]
    assert snapshot["search_results"] == []
    assert snapshot["first_result"] is None


def test_observe_browser_ignores_result_hidden_by_ancestor(executor: ActionExecutor) -> None:
    assert executor._page is not None
    executor._page.set_content(
        """
        <main><ol id="b_results">
          <div style="display:none">
            <li class="b_algo"><h2><a href="https://hidden.example">Hidden first</a></h2></li>
          </div>
          <li class="b_algo"><h2><a href="https://visible.example">Visible first</a></h2></li>
        </ol></main>
        """,
        wait_until="domcontentloaded",
    )

    snapshot = executor.observe_browser()

    assert snapshot["first_result_title"] == "Visible first"
    assert snapshot["first_result_url"] == "https://visible.example/"


def test_observe_browser_reports_main_document_status_when_known(
    executor: ActionExecutor,
) -> None:
    assert executor._page is not None
    executor._page.route(
        "https://fixture.test/**",
        lambda route: route.fulfill(
            status=207,
            content_type="text/html",
            body="<title>HTTP fixture</title><main><h1>Ready</h1></main>",
        ),
    )
    executor._page.goto("https://fixture.test/current", wait_until="domcontentloaded")

    snapshot = executor.observe_browser()

    assert snapshot["url"] == "https://fixture.test/current"
    assert snapshot["http_status"] == 207
    assert snapshot["title"] == "HTTP fixture"


def test_observe_browser_extracts_structured_results_from_rss(executor: ActionExecutor) -> None:
    assert executor._page is not None
    executor._page.route(
        "https://fixture.test/search**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/rss+xml",
            body="""<?xml version="1.0" encoding="utf-8"?>
              <rss version="2.0"><channel>
                <title>Bing: São Lourenço da Mata</title>
                <item>
                  <title>Prefeitura de São Lourenço da Mata</title>
                  <link>https://saolourencodamata.example/</link>
                  <description>Informação municipal.</description>
                </item>
                <item>
                  <title>São Lourenço da Mata — IBGE</title>
                  <link>https://ibge.example/sao-lourenco</link>
                  <description>Dados geográficos.</description>
                </item>
              </channel></rss>""",
        ),
    )
    executor._page.goto(
        "https://fixture.test/search?format=rss&q=S%C3%A3o+Louren%C3%A7o+da+Mata",
        wait_until="domcontentloaded",
    )

    snapshot = executor.observe_browser()

    assert snapshot["search_results"] == [
        {
            "title": "Prefeitura de São Lourenço da Mata",
            "url": "https://saolourencodamata.example/",
        },
        {
            "title": "São Lourenço da Mata — IBGE",
            "url": "https://ibge.example/sao-lourenco",
        },
    ]
    assert snapshot["first_result"] == snapshot["search_results"][0]


def test_observe_browser_prefers_atom_alternate_and_default_links(
    executor: ActionExecutor,
) -> None:
    assert executor._page is not None
    executor._page.route(
        "https://fixture.test/atom**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/atom+xml",
            body="""<?xml version="1.0" encoding="utf-8"?>
              <feed xmlns="http://www.w3.org/2005/Atom">
                <title>Busca Atom</title>
                <entry>
                  <title>Resultado com alternate</title>
                  <link rel="self" href="https://fixture.test/atom/entry-1" />
                  <link rel="alternate" href="https://example.org/result-1" />
                </entry>
                <entry>
                  <title>Resultado com link padrão</title>
                  <link rel="self" href="https://fixture.test/atom/entry-2" />
                  <link href="https://example.org/result-2" />
                </entry>
              </feed>""",
        ),
    )
    executor._page.goto("https://fixture.test/atom?q=teste", wait_until="domcontentloaded")

    snapshot = executor.observe_browser()

    assert snapshot["search_results"] == [
        {"title": "Resultado com alternate", "url": "https://example.org/result-1"},
        {"title": "Resultado com link padrão", "url": "https://example.org/result-2"},
    ]


def test_observe_browser_requires_an_existing_page() -> None:
    executor = ActionExecutor(headless=True)

    with pytest.raises(RuntimeError, match="Navegador não inicializado"):
        executor.observe_browser()


@pytest.mark.parametrize(
    "limits",
    [
        {"max_text_chars": 0},
        {"max_links": 0},
        {"max_results": 0},
    ],
)
def test_observe_browser_rejects_non_positive_limits(limits: dict[str, int]) -> None:
    executor = ActionExecutor(headless=True)

    with pytest.raises(ValueError, match="devem ser positivos"):
        executor.observe_browser(**limits)
