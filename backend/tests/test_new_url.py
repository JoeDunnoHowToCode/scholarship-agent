"""找新網址（ADR-080）：換網址前確認是同一個學程。"""

from app.features.discovery.new_url import same_programme

CYBER = ["Master of Applied Cybersecurity", "Erasmus Mundus Joint Master Degree Scholarship – CyberMACS"]


def test_same_programme_when_name_and_provider_appear() -> None:
    page = "CyberMACS – Erasmus Mundus Master of Applied Cybersecurity. Offered by the CyberMACS Consortium."
    assert same_programme(CYBER, "CyberMACS Consortium", page) is True


def test_names_match_ignoring_case_and_punctuation() -> None:
    page = "Welcome to RE PLAY - European Joint Masters in Games! Applications open soon."
    assert same_programme(["RE_PLAY: EUROPEAN JOINT MASTERS IN GAMES"], None, page) is True


def test_a_different_programme_is_not_the_same() -> None:
    page = "Erasmus Mundus Master in Data Science. Offered by the DSE Consortium."
    assert same_programme(CYBER, "CyberMACS Consortium", page) is False


def test_the_distinctive_provider_word_must_appear() -> None:
    # 名稱對上了，但主辦單位（波爾圖大學）沒出現：可能是別人轉貼的頁面，不換
    page = "Master of Applied Cybersecurity scholarships explained by a blog."
    assert same_programme(CYBER, "Universidade do Porto", page) is False
    # 主辦單位只有通用的字（European Commission）：只看名稱
    assert same_programme(CYBER, "European Commission", page) is True
