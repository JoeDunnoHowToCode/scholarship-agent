"""個人資料頁的國家選單（ADR-091）：後端提供完整的國碼＋中文名稱清單，前端不自己維護。"""

from app.features.profiles import api


def test_country_options_have_codes_and_chinese_names_sorted() -> None:
    options = api.list_countries()
    codes = [o.code for o in options]
    assert len(codes) == len(set(codes)) > 200  # ISO 3166 約 249 個，再加 Kosovo
    by_code = {o.code: o.name for o in options}
    assert by_code["TW"] == "台灣"  # 我們自己的中文名稱，不是 pycountry 的寫法
    assert by_code["XK"] == "科索沃"  # ISO 沒有、但我們接受的代碼也要選得到
    assert by_code["SE"] == "瑞典"
    assert codes == sorted(codes)  # 依國碼排序；中文名稱的排序交給瀏覽器（localeCompare，和列表的國家選單一樣）
