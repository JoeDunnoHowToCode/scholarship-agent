"""EACEA 目錄頁解析的單元測試（ADR-031：清單頁 → 學程名稱與網址）。"""

from app.features.sources import catalogue


def test_parse_catalogue_uses_title_link() -> None:
    # 一般卡片：標題本身就是連到學程官網的 <a>；名稱裡多餘的空白要收成一格。
    # 沒有 ecl-card 的 <article> 不是學程卡片，要略過
    html = """
    <article class="ecl-card"><div class="ecl-card__body"><div class="ecl-content-block ecl-card__content-block">
     <div class="ecl-content-block__title">
      <a class="ecl-link ecl-link--standalone ecl-link--icon" href="https://www.multidiverse.eu/"><span class="ecl-link__label">Erasmus Mundus Joint Master in
        Multilingualism and Cultural Diversity</span><span class="wt-icon--external ecl-icon"></span></a>
     </div>
     <div class="ecl-content-block__description"><p>MultiDiverse - Project overview<br/><a href="https://erasmus-plus.ec.europa.eu/projects/search/details/101241136">https://erasmus-plus.ec.europa.eu/projects/search/details/101241136</a></p></div>
    </div></div></article>
    <article class="other"><a href="https://example.org/">不是學程卡片</a></article>
    """
    assert catalogue.parse_catalogue(html) == [
        catalogue.CatalogueEntry(
            name="Erasmus Mundus Joint Master in Multilingualism and Cultural Diversity",
            url="https://www.multidiverse.eu/",
        )
    ]


def test_parse_catalogue_falls_back_to_description_link() -> None:
    # 真實網站 218 張卡片裡有 7 張標題沒有連結，官網網址只出現在說明文字裡
    html = """
    <article class="ecl-card"><div class="ecl-card__body"><div class="ecl-content-block ecl-card__content-block">
     <div class="ecl-content-block__title">Strengthening Mobility and Promoting Regional Integration of Engineering Education in Africa</div>
     <div class="ecl-content-block__description"><p>SPREE - <a href="http://www.spreeafrica.com/">http://www.spreeafrica.com/</a></p></div>
    </div></div></article>
    """
    assert catalogue.parse_catalogue(html) == [
        catalogue.CatalogueEntry(
            name="Strengthening Mobility and Promoting Regional Integration of Engineering Education in Africa",
            url="http://www.spreeafrica.com/",
        )
    ]


def test_parse_catalogue_never_uses_the_project_page() -> None:
    # erasmus-plus.ec.europa.eu 的專案介紹頁不是學程官網，不能當網址：
    # 第一張卡片要跳過它、改用後面的官網連結；第二張只有專案頁，整張略過
    html = """
    <article class="ecl-card"><div class="ecl-card__body"><div class="ecl-content-block ecl-card__content-block">
     <div class="ecl-content-block__title">Joint Master in Example Studies</div>
     <div class="ecl-content-block__description"><p>EXAMPLE - <a href="https://erasmus-plus.ec.europa.eu/projects/search/details/101000001">project overview</a> <a href="https://example-master.eu/">https://example-master.eu/</a></p></div>
    </div></div></article>
    <article class="ecl-card"><div class="ecl-card__body"><div class="ecl-content-block ecl-card__content-block">
     <div class="ecl-content-block__title">Joint Master Without Homepage</div>
     <div class="ecl-content-block__description"><p>NOHOME - <a href="https://erasmus-plus.ec.europa.eu/projects/search/details/101000002">project overview</a></p></div>
    </div></div></article>
    """
    assert catalogue.parse_catalogue(html) == [
        catalogue.CatalogueEntry(
            name="Joint Master in Example Studies",
            url="https://example-master.eu/",
        )
    ]
