"""一次性的建置腳本：從各國官方名單抓高等教育機構，寫成種子 CSV。

用法（在 backend/ 底下）：
    uv run python scripts/build_universities.py

輸出：app/features/discovery/universities.csv
欄位：country,region,name,homepage,source_url,note

為什麼要這份名單：探索 agent 要知道「哪些學校是官方承認的」，才不會把來路不明的
網站當成獎學金來源。名單只從政府或主管機關的官方頁面來，不自己猜。

抓取規矩（ADR-028）：一律用專案的 HttpFetcher，它會先讀 robots.txt、
遵守 Crawl-delay、同一個網站兩次請求至少隔 5 秒；被擋（BlockedError）就停下來回報，
不換手法、不假裝成瀏覽器。芬蘭 opintopolku.fi 的 robots.txt 要求隔 30 秒，
HttpFetcher 會自動照做，所以整支腳本大約要跑 20 分鐘。

任何一個來源失敗，整支腳本就停下來、不覆寫 CSV，避免寫出「少了一個國家」卻沒人發現的檔案。
"""

import csv
import io
import json
import re
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup, Tag

# 腳本放在 backend/scripts/，直接執行時 Python 只會在 scripts/ 裡找模組；
# 把 backend/ 加進搜尋路徑，才能 import 專案的 app 套件
BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.core.fetch.base import BlockedError, FetchResult, TemporaryFetchError
from app.core.fetch.http import HttpFetcher

OUTPUT = BACKEND / "app" / "features" / "discovery" / "universities.csv"
COLUMNS = ["country", "region", "name", "homepage", "source_url", "note"]


@dataclass(frozen=True)
class Row:
    """CSV 的一列：一所學校。"""

    country: str  # ISO 國碼
    region: str  # 只有英國填（England／Scotland／Wales／Northern Ireland）
    name: str
    homepage: str  # 只留「協定 + 主機名稱」，例如 https://www.surrey.ac.uk
    source_url: str  # 這一列來自哪一個官方名單
    note: str = ""


# ---------------------------------------------------------------- 共用小工具


def homepage_of(url: str) -> str:
    """把網址縮成首頁：去掉路徑、查詢參數（追蹤碼）和結尾斜線，主機名稱照來源給的。

    例：https://www.gu.se/english/?languageId=100001 → https://www.gu.se
    """
    parts = urlsplit(url.strip())
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}"


# 這些是「兩層的公共後綴」：ac.uk 底下每個學校各自註冊，所以要看最後三段
_TWO_LEVEL_SUFFIXES = {"ac.uk", "co.uk", "org.uk", "gov.uk"}


def registrable_domain(homepage: str) -> str:
    """可註冊網域：用來判斷兩列是不是同一所學校。

    例：www2.mmu.ac.uk → mmu.ac.uk；en.uit.no → uit.no
    只處理這六國會遇到的後綴，不是完整的公共後綴清單（夠用就好）。
    """
    labels = urlsplit(homepage).netloc.split(".")
    keep = 3 if ".".join(labels[-2:]) in _TWO_LEVEL_SUFFIXES else 2
    return ".".join(labels[-keep:])


def get(fetcher: HttpFetcher, url: str) -> FetchResult:
    """抓一頁；連線逾時這類暫時的網路問題最多試三次。

    芬蘭那段要跑 20 分鐘，中途網路晃一下就整個重來太浪費。
    重試之間的間隔仍由 HttpFetcher 控制（同一網站至少隔 5 秒或 Crawl-delay），不會變成狂打。
    被擋（BlockedError）不重試，直接往上丟。
    """
    for attempt in range(3):
        try:
            return fetcher.get(url)
        except (httpx.TransportError, TemporaryFetchError) as error:
            if attempt == 2:
                raise
            print(f"  ~ 暫時失敗（{type(error).__name__}），再試一次：{url}", flush=True)
    raise AssertionError("不會走到這裡")


def soup_of(fetcher: HttpFetcher, url: str) -> BeautifulSoup:
    return BeautifulSoup(get(fetcher, url).content, "html.parser")


def json_of(fetcher: HttpFetcher, url: str) -> object:
    return json.loads(get(fetcher, url).content)


def href_of(tag: Tag) -> str:
    """連結的網址（BeautifulSoup 的屬性型別比較寬，這裡統一轉成字串）。"""
    return str(tag.get("href") or "")


def clean_text(tag: Tag) -> str:
    """標籤裡的文字，把換行和多個空白縮成一個空白。"""
    return re.sub(r"\s+", " ", tag.get_text(" ")).strip()


# ---------------------------------------------------------------- 英格蘭（OfS）

OFS_URL = "https://register-api.officeforstudents.org.uk/api/Provider"

# OfS 的 LegalName 是法人名稱，有些跟大家熟悉的校名差很多
# （例如劍橋的法人名稱是 "The Chancellor, Masters, and Scholars of the University of Cambridge"）。
# 這裡用同一筆資料 TradingName（對外使用的名稱）裡的某一行來取代；
# 程式會檢查這行字真的出現在來源的 TradingName 裡，所以名稱仍然來自官方資料。
# 鍵是 UKPRN（英國學校的固定編號），不會因為改名而變。
OFS_NAME_FROM_TRADING = {
    "10003758": "London Academy of Music and Dramatic Art",  # 法人名 Lamda Limited
    "10007788": "The University of Cambridge",
    "10007774": "The University of Oxford",
    "10003270": "Imperial College London",  # 法人名 Imperial College of Science, Technology and Medicine
    "10007799": "Newcastle University",  # 法人名 University of Newcastle upon Tyne
    "10007767": "Keele University",
    "10007768": "Lancaster University",
    "10037449": "Plymouth Marjon University",  # 法人名 University of St Mark & St John
    "10005553": "Royal Holloway, University of London",  # 法人名 Royal Holloway and Bedford New College
    "10007164": "University of the West of England",
    "10002718": "Goldsmiths, University of London",  # 法人名 Goldsmiths' College
    "10008173": "University of the Built Environment",  # 法人名 University College of Estate Management
    "10001282": "Northumbria University",
    "10007143": "Durham University",
    "10007780": "SOAS University of London",
    "10007760": "Birkbeck, University of London",  # 法人名 Birkbeck College
    "10035638": "Institute of Contemporary Music Performance",  # 法人名 ICMP Management Limited
    "10007776": "University of Roehampton",
    "10008071": "Architectural Association School of Architecture",
    "10005470": "Richmond, The American International University in London",
    "10067355": "The Dyson Institute of Engineering and Technology",  # 法人名 Dyson Technical Training Limited
    "10090839": "The National Institute of Teaching",  # 法人名 School-Led Development Trust
}


def clean_legal_name(name: str) -> str:
    """把法人名稱整理成校名：去掉公司型態字尾，把結尾的 ", the" 或 "(The)" 移到前面。

    例：University of Nottingham, the → The University of Nottingham
        Middlesex University Higher Education Corporation → Middlesex University
    """
    name = name.strip()
    for suffix in (" Higher Education Corporation", " Limited", " Ltd", ", Inc."):
        name = name.removesuffix(suffix)
    match = re.fullmatch(r"(.+?)(?:, the| \(the\))", name, flags=re.IGNORECASE)
    if match:
        name = "The " + match.group(1)
    return name


def england(fetcher: HttpFetcher) -> list[Row]:
    providers = json_of(fetcher, OFS_URL)
    assert isinstance(providers, list)
    rows = []
    for p in providers:
        # 欄位值有時候後面多了空白（例如 "Research "），先 strip 再比較
        if (p.get("RegistrationStatus") or "").strip() != "Registered":
            continue
        # 只留有「授課型碩士」或「研究型」學位授予權的學校；
        # Bachelor's／Foundation 只能頒學士或副學士，跟碩士獎學金無關
        powers = (p.get("HighestLevelOfDegreeAwardingPowers") or "").strip()
        if not powers.startswith(("Taught", "Research")):
            continue
        ukprn = p["Ukprn"]
        if ukprn in OFS_NAME_FROM_TRADING:
            name = OFS_NAME_FROM_TRADING[ukprn]
            trading = [line.strip() for line in (p.get("TradingName") or "").split("\n")]
            assert name in trading, f"OfS {ukprn} 的 TradingName 裡沒有「{name}」，請更新對照表"
        else:
            name = clean_legal_name(p["LegalName"])
        rows.append(Row("GB", "England", name, homepage_of(p["Website"]), OFS_URL))
    return rows


# ---------------------------------------------------------------- 蘇格蘭

SCOTLAND_URL = "https://www.gov.scot/policies/universities/"


def scotland(fetcher: HttpFetcher) -> list[Row]:
    soup = soup_of(fetcher, SCOTLAND_URL)
    heading = soup.find("h3", string=re.compile("Recognised bodies"))
    assert isinstance(heading, Tag), "蘇格蘭頁面找不到 Recognised bodies 段落"
    rows = []
    # 從「Recognised bodies」標題往下讀，讀到「based elsewhere in the UK」那段為止。
    # 中間有兩個清單：有學位授予權的 recognised bodies，
    # 以及透過合作學校頒學位的 The Glasgow School of Art（也有碩士課程，一起收）
    for sibling in heading.find_next_siblings():
        if "based elsewhere" in sibling.get_text():
            break
        if sibling.name == "ul":
            for a in sibling.find_all("a", href=True):
                rows.append(Row("GB", "Scotland", clean_text(a), homepage_of(href_of(a)), SCOTLAND_URL))
    return rows


# ---------------------------------------------------------------- 威爾斯

WALES_URL = "https://www.gov.uk/check-university-award-degree/recognised-bodies-wales"

# 不收的 recognised bodies 與原因
WALES_SKIP = {
    "Royal College of Nursing": "護理專業團體，不是一般大學",
    "University of Wales": "已不再招生，只替舊學生頒學位",
    "Open University, The": "英格蘭名單已有（同一所學校）",
}


def wales(fetcher: HttpFetcher) -> list[Row]:
    soup = soup_of(fetcher, WALES_URL)
    body = soup.find("div", class_="gem-c-govspeak")
    assert isinstance(body, Tag), "威爾斯頁面找不到名單本文"
    rows = []
    for a in body.find_all("a", href=True):
        # 名稱後面括號是威爾斯文校名，例如 "Bangor University (Prifysgol Bangor)"，只留英文
        name = re.sub(r"\s*\(.*\)$", "", clean_text(a))
        if name in WALES_SKIP:
            continue
        rows.append(Row("GB", "Wales", name, homepage_of(href_of(a)), WALES_URL))
    return rows


# ---------------------------------------------------------------- 北愛爾蘭

NI_URL = "https://www.economy-ni.gov.uk/articles/higher-education-policy"


def northern_ireland(fetcher: HttpFetcher) -> list[Row]:
    soup = soup_of(fetcher, NI_URL)
    rows = []

    # 一、recognised bodies（有學位授予權）：在「Current Northern Ireland recognised bodies are:」
    #    這段之後，到「In addition to institutions」之前，每段一個連結
    start = soup.find("p", string=re.compile("recognised bodies are"))
    assert isinstance(start, Tag), "北愛頁面找不到 recognised bodies 段落"
    for p in start.find_next_siblings("p"):
        if "In addition to institutions" in p.get_text():
            break
        a = p.find("a", href=True)
        if not isinstance(a, Tag):
            continue
        name = clean_text(a)
        if name == "Open University":
            continue  # 英格蘭名單已有
        rows.append(Row("GB", "Northern Ireland", name, homepage_of(href_of(a)), NI_URL))

    # 二、listed bodies 裡的兩所 University College（St Mary's、Stranmillis）：
    #    它們是教育學院，學位由 Queen's University 頒發，但是正式的大學層級學校，有碩士課程。
    #    其他 listed bodies 是技職學院或研究機構，不收
    for li in soup.find_all("li"):
        a = li.find("a", href=True)
        if isinstance(a, Tag) and "University College" in clean_text(a):
            rows.append(Row("GB", "Northern Ireland", clean_text(a), homepage_of(href_of(a)), NI_URL))
    return rows


# ---------------------------------------------------------------- 瑞典

SE_HEI_URL = (
    "https://www.uka.se/swedish-higher-education-authority/about-higher-education/"
    "universities-university-colleges-and-other-education-providers/higher-education-institutions"
)
# UKÄ「所有學位授予權」Excel 的連結放在這一頁；檔名會隨更新日期改變，所以每次都從頁面找
SE_RIGHTS_PAGE = "https://www.uka.se/integrationer/examenstillstand"

# 英文名單頁用英文校名，學位授予權 Excel 用瑞典文校名，兩邊對不起來，只好手寫對照表。
# 鍵：英文名單頁上的校名（去掉 " website"）；值：Excel 裡的瑞典文校名
SE_NAME_MAP = {
    # Universities
    "Chalmers University of Technology": "Chalmers tekniska högskola",
    "Karlstad University": "Karlstads universitet",
    "Karolinska Institutet": "Karolinska institutet",
    "KTH Royal Institute of Technology": "Kungl. Tekniska högskolan",
    "Linköping University": "Linköpings universitet",
    "Linnaeus University": "Linnéuniversitetet",
    "Luleå University of Technology": "Luleå tekniska universitet",
    "Lund University": "Lunds universitet",
    "Malmö University": "Malmö universitet",
    "Mid Sweden University": "Mittuniversitetet",
    "Stockholm School of Economics": "Handelshögskolan i Stockholm",
    "Stockholm University": "Stockholms universitet",
    "Swedish University of Agricultural Sciences": "Sveriges lantbruksuniversitet",
    "Umeå University": "Umeå universitet",
    "University of Gothenburg": "Göteborgs universitet",
    "Uppsala University": "Uppsala universitet",
    "Örebro University": "Örebro universitet",
    "Mälardalen University": "Mälardalens universitet",
    # University colleges
    "Blekinge Institute of Technology": "Blekinge tekniska högskola",
    "Dalarna University": "Högskolan Dalarna",
    "Halmstad University": "Högskolan i Halmstad",
    "Jönköping University": "Stiftelsen Högskolan i Jönköping",
    "Kristianstad University": "Högskolan Kristianstad",
    "Swedish Defence University": "Försvarshögskolan",
    "Södertörn University": "Södertörns högskola",
    "The Swedish School of Sport and Health Sciences": "Gymnastik- och idrottshögskolan",
    "University of Borås": "Högskolan i Borås",
    "University of Gävle": "Högskolan i Gävle",
    "University of Skövde": "Högskolan i Skövde",
    "University West": "Högskolan Väst",
    # Art, design and music academies
    "Beckmans College of Design": "Beckmans Designhögskola",
    "Konstfack": "Konstfack",
    "Royal College of Music in Stockholm": "Kungl. Musikhögskolan i Stockholm",
    "Royal Institute of Art": "Kungl. Konsthögskolan",
    "Stockholm University of the Arts": "Stockholms konstnärliga högskola",
    # Independent education providers
    "Brunnsvik Folk High School": "Brunnsviks folkhögskola",
    "Erica Foundation": "Ericastiftelsen",
    "Marie Cederschiöld University": "Marie Cederschiöld högskola",
    "Johannelund School of Theology": "Johannelunds teologiska högskola",
    "Newman Institute": "Newmaninstitutet",
    "Sophiahemmet University College": "Sophiahemmet Högskola",
    "Stockholm University College of Music Education": "Stiftelsen Stockholms Musikpedagogiska Institut",
    "Swedish Institute for CBT & Schema Therapy": "Svenska institutet för kognitiv psykoterapi",
    "Swedish Red Cross University College": "Röda Korsets Högskola",
    "University College Stockholm": "Enskilda Högskolan Stockholm",
    "World Maritime University": "Världssjöfartsuniversitetet",
    "Örebro School of Theology": "Akademi för ledarskap och teologi",  # altutbildning.se = ALT
}

# 名單頁上分組的標題；只收這四組裡的連結（頁尾的「About ...」等連結不算）
SE_SECTIONS = {
    "Universities",
    "University colleges",
    "Art, design and music academies",
    "Independent education providers",
}


def read_xlsx_rows(data: bytes) -> list[list[str]]:
    """不用另外裝套件，直接讀 xlsx：它其實是一個 zip，裡面是 XML。

    文字儲存格只存編號，真正的字放在 sharedStrings.xml，要查表換回來。
    這裡讀「最後一張」工作表（UKÄ 的檔案第一張是說明，第二張才是資料）。
    """
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        shared = [
            "".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t"))
            for si in ElementTree.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns)
        ]
        sheets = sorted(n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
        sheet = ElementTree.fromstring(z.read(sheets[-1]))
    rows = []
    for row in sheet.iter(f"{{{ns['m']}}}row"):
        values = []
        for cell in row.findall("m:c", ns):
            v = cell.find("m:v", ns)
            text = v.text if v is not None and v.text else ""
            values.append(shared[int(text)] if cell.get("t") == "s" and text else text)
        rows.append(values)
    return rows


def sweden_master_rights(fetcher: HttpFetcher) -> set[str]:
    """有碩士（Masterexamen，含 Konstnärlig masterexamen）或一年制碩士（Magisterexamen）授予權的學校。"""
    page = soup_of(fetcher, SE_RIGHTS_PAGE)
    link = page.find("a", href=re.compile(r"_alla_.*\.xlsx$"))
    assert isinstance(link, Tag), "UKÄ 頁面找不到「Alla examenstillstånd」的 Excel 連結"
    xlsx = get(fetcher, urljoin(SE_RIGHTS_PAGE, href_of(link))).content
    schools = set()
    for values in read_xlsx_rows(xlsx)[1:]:  # 第一列是標題
        if len(values) >= 2 and re.search(r"(?i)(master|magister)examen", values[1]):
            schools.add(values[0].strip())
    return schools


def sweden(fetcher: HttpFetcher) -> list[Row]:
    rights = sweden_master_rights(fetcher)
    soup = soup_of(fetcher, SE_HEI_URL)
    rows = []
    section = ""
    # 照頁面順序走過標題和連結：遇到標題就記下現在在哪一組
    for tag in soup.find_all(["h2", "h3", "a"]):
        if tag.name != "a":
            section = clean_text(tag)
            continue
        href = href_of(tag)
        if section not in SE_SECTIONS or not href.startswith("http"):
            continue
        name = clean_text(tag).removesuffix(" website")
        name = re.sub(r"\s*\(.*\)$", "", name)  # 去掉「(former ...)」這類舊名說明
        swedish = SE_NAME_MAP.get(name)
        if swedish is None:
            print(f"  ! 瑞典：「{name}」不在對照表，略過；請補進 SE_NAME_MAP")
            continue
        if swedish not in rights:
            print(f"  - 瑞典：{name} 沒有碩士學位授予權，不收")
            continue
        rows.append(Row("SE", "", name, homepage_of(href), SE_HEI_URL))
    return rows


# ---------------------------------------------------------------- 芬蘭

FI_SEARCH = "https://opintopolku.fi/konfo-backend/search/oppilaitokset?koulutustyyppi={}&size=100"
FI_DETAIL = "https://opintopolku.fi/konfo-backend/oppilaitos/{}"

# 不收的學校（用芬蘭文校名當鍵）與原因
FI_SKIP = {
    "Pelastusopisto": "Emergency Services Academy：消防救災的職業訓練，不頒碩士",
}

# opintopolku 給的網址有些不是學校首頁，而是客服或子網站；這裡改成學校的主網域。
# 鍵：opintopolku 給的網址主機；值：改用的首頁。每一筆都寫原因
FI_HOMEPAGE_OVERRIDE = {
    # 赫爾辛基大學填的是學生客服入口 uni-help.helsinki.fi，學校首頁是 www.helsinki.fi
    "uni-help.helsinki.fi": "https://www.helsinki.fi",
}


def finland(fetcher: HttpFetcher) -> list[Row]:
    rows = []
    # yo＝大學（yliopisto），amk＝應用科學大學（ammattikorkeakoulu），兩種都有碩士
    for kind in ("yo", "amk"):
        search_url = FI_SEARCH.format(kind)
        result = json_of(fetcher, search_url)
        assert isinstance(result, dict)
        hits = result["hits"]
        assert len(hits) == result["total"], f"芬蘭 {kind} 有 {result['total']} 筆但只拿到 {len(hits)} 筆，要分頁"
        for hit in hits:
            oid = hit["oid"]
            names = hit.get("nimi") or {}
            name = str(names.get("en") or names.get("fi"))
            if names.get("fi") in FI_SKIP:
                print(f"  - 芬蘭：{name} 不收（{FI_SKIP[names['fi']]}）")
                continue
            detail = json_of(fetcher, FI_DETAIL.format(oid))
            assert isinstance(detail, dict)
            www = finland_www(detail)
            if not www:
                print(f"  ! 芬蘭：{name} 沒有網址，略過")
                continue
            homepage = homepage_of(www)
            homepage = FI_HOMEPAGE_OVERRIDE.get(urlsplit(homepage).netloc, homepage)
            rows.append(Row("FI", "", name, homepage, search_url))
    return rows


def finland_www(detail: dict[str, object]) -> str | None:
    """oppilaitos.metadata.yhteystiedot 裡的網址，優先拿英文版（en），沒有再拿芬蘭文（fi）。

    yhteystiedot（聯絡資料）有時是一個物件、有時是清單，兩種都處理。
    """
    oppilaitos = detail.get("oppilaitos") or {}
    assert isinstance(oppilaitos, dict)
    contacts = (oppilaitos.get("metadata") or {}).get("yhteystiedot") or []
    if isinstance(contacts, dict):
        contacts = [contacts]
    for lang in ("en", "fi", "sv"):
        for contact in contacts:
            www = (contact.get("www") or {}).get(lang)
            if www:
                return str(www)
    return None


# ---------------------------------------------------------------- 丹麥

DK_API = "https://ufmembedheidb-bqayg6drg9f2bsbu.northeurope-01.azurewebsites.net/api/data/institutions"
DK_LIST_URL = DK_API + "?limit=500"

# 「Institution in architecture or art」這一類裡，只收明確有碩士學位的學校。
# 依據：
# - 前三所：丹麥高教署的類別頁
#   https://ufsn.dk/english/education/the-higher-education-system/institutions-in-architecture-and-art/
#   寫明這三所在建築、設計、修復領域頒學士、碩士、博士。
# - 四所音樂學院和皇家美術學院：屬文化部管轄，丹麥的音樂學院有兩年制碩士（kandidat／MMus），
#   皇家美術學院是學士三年＋碩士三年（BFA／MFA）。這是 Claude 依一般知識判斷，
#   文化部的法規頁（retsinformation.dk）有 captcha 擋住，沒辦法用程式再確認，請人工複查。
# 不收：國家電影學校、表演藝術學校、菲因與日德蘭兩所美術學院、作家學校，
#   它們頒的是學校自己的文憑或只有學士，不是明確的碩士學位。
DK_ART_WITH_MASTERS = {
    "The Royal Danish Academy - Architecture, Design, Conservation",
    "Aarhus School of Architecture",
    "Kolding School of Design",
    "The Royal Danish Academy of Music",
    "The Royal Academy of Music",  # 奧胡斯的 Det Jyske Musikkonservatorium
    "Danish National Academy of Music",
    "Rhythmic Music Conservatory",
    "The Royal Danish Academy of Fine Arts, Schools of Visual Art",
}


def denmark(fetcher: HttpFetcher) -> list[Row]:
    listing = json_of(fetcher, DK_LIST_URL)
    assert isinstance(listing, dict)
    items = listing["items"]
    assert len(items) == listing["total"], "丹麥名單沒有一次拿完，要分頁"
    rows = []
    seen_art = set()
    for item in items:
        if item.get("status") != "Current":  # Historic＝已合併或關閉的學校
            continue
        # 名單只有名稱，類別和網址要再查一次單筆資料（網頁本身也是這樣查的：?instid=編號）
        detail = json_of(fetcher, f"{DK_API}?instid={item['instId']}")
        assert isinstance(detail, dict)
        types = {t["type"] for t in detail.get("types") or []}
        name = detail["instNameEn"] if detail.get("instNameEn") not in (None, "", "-") else detail["instNameDa"]
        if "University" in types:
            keep = True
        elif "Institution in architecture or art" in types:
            keep = name in DK_ART_WITH_MASTERS
            seen_art.add(name)
        else:
            # Business academy、University college、Maritime 等只頒專業學士，不收
            keep = False
        if keep:
            rows.append(Row("DK", "", name, homepage_of(detail["instUrl"]), DK_LIST_URL))
    missing = DK_ART_WITH_MASTERS - seen_art
    assert not missing, f"丹麥藝術類對照表裡的名稱在來源找不到：{missing}"
    return rows


# ---------------------------------------------------------------- 挪威

NO_URL = "https://www.nokut.no/en/higher-education/higher-education-institutions/"

# 只收前三組；第四組「University Colleges with accredited study programmes」只有個別學程認證，
# 不是整所學校獲得認可，不收
NO_SECTIONS = ("Universities", "Specialised Universities", "University Colleges/Universitites of Applied Sciences")


def norway(fetcher: HttpFetcher) -> list[Row]:
    soup = soup_of(fetcher, NO_URL)
    rows = []
    section = ""
    # 每一組是一個可展開的區塊，標題是指向 #collapsibleContent_... 的連結
    for a in soup.find_all("a", href=True):
        if href_of(a).startswith("#collapsibleContent"):
            section = clean_text(a)
            continue
        if section in NO_SECTIONS and href_of(a).startswith("http"):
            rows.append(Row("NO", "", clean_text(a), homepage_of(href_of(a)), NO_URL))
    return rows


# ---------------------------------------------------------------- 冰島

IS_URL = "https://www.stjornarradid.is/verkefni/menntamal/haskolar/"
IS_NOTE = "首頁由人工確認"

# 冰島教育部的頁面只有校名，沒有連結，所以首頁是人工確認後寫死的（使用者同意，2026-11-08）。
# 確認方法：用 HttpFetcher 打開首頁，網頁文字裡要有這個校名。下面執行時會再檢查一次。
# 官方頁面列了七所，有兩所沒收：
# - Landbúnaðarháskóli Íslands（www.lbhi.is）：網站回 captcha，照規定不繞過，無法確認
# - Háskólinn á Hólum（www.holar.is）：會轉到 hi.is 的「Háskóli Íslands á Hólum」頁面，
#   已併入冰島大學的大學集團，首頁跟冰島大學同一個網域，算重複
IS_VERIFIED = {
    "Háskóli Íslands": "https://hi.is",  # www.hi.is 會轉到 hi.is
    "Háskólinn á Akureyri": "https://www.unak.is",
    "Háskólinn í Reykjavík": "https://www.ru.is",
    "Listaháskóli Íslands": "https://www.lhi.is",
    "Háskólinn á Bifröst": "https://www.bifrost.is",
}


def iceland(fetcher: HttpFetcher) -> list[Row]:
    source_text = soup_of(fetcher, IS_URL).get_text(" ")
    rows = []
    for name, homepage in IS_VERIFIED.items():
        if name not in source_text:
            print(f"  ! 冰島：官方頁面已經沒有「{name}」，不收")
            continue
        page_text = BeautifulSoup(get(fetcher, homepage).content, "html.parser").get_text(" ")
        if name not in page_text:
            print(f"  ! 冰島：{homepage} 的網頁裡找不到「{name}」，不收，請人工複查")
            continue
        rows.append(Row("IS", "", name, homepage, IS_URL, IS_NOTE))
    return rows


# ---------------------------------------------------------------- 主程式

SOURCES = [
    ("England", england),
    ("Scotland", scotland),
    ("Wales", wales),
    ("Northern Ireland", northern_ireland),
    ("Sweden", sweden),
    ("Denmark", denmark),
    ("Norway", norway),
    ("Iceland", iceland),
    ("Finland", finland),  # 最慢（每次請求隔 30 秒），放最後
]


def dedupe(rows: list[Row]) -> list[Row]:
    """同一個可註冊網域只留一列：排序後先出現的那列。

    英國四個地區都列了 Open University；地區排序 England 在最前面，所以留下英格蘭那列。
    """
    kept: dict[str, Row] = {}
    for row in sorted(rows, key=lambda r: (r.country, r.region, r.name)):
        domain = registrable_domain(row.homepage)
        if domain in kept:
            print(f"  = 重複網域 {domain}：留「{kept[domain].name}」，去掉「{row.name}」（{row.region or row.country}）")
            continue
        kept[domain] = row
    return list(kept.values())


def main() -> None:
    started = time.monotonic()
    fetcher = HttpFetcher(5.0)
    rows: list[Row] = []
    try:
        for label, build in SOURCES:
            print(f"{label} ...", flush=True)
            found = build(fetcher)
            print(f"  {len(found)} 所", flush=True)
            rows.extend(found)
    except BlockedError as error:
        # 被擋就停（ADR-028），不覆寫舊的 CSV
        sys.exit(f"被擋住了（{error.reason}），停止，CSV 沒有更新")
    finally:
        fetcher.close()

    rows = dedupe(rows)
    with OUTPUT.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(COLUMNS)
        for row in rows:
            writer.writerow([row.country, row.region, row.name, row.homepage, row.source_url, row.note])
    print(f"寫入 {len(rows)} 列到 {OUTPUT}，花了 {time.monotonic() - started:.0f} 秒")


if __name__ == "__main__":
    main()
