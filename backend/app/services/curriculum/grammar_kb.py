"""Grammar pattern knowledge base for index-only entries (no Gemini)."""

from __future__ import annotations

# pattern_key (normalized) -> (meaning, connection_rule, example_jp, example_zh, jlpt)
GRAMMAR_KB: dict[str, tuple[str, str, str, str, str]] = {
    "〜からには": (
        "既然…就必須…",
        "Vた / N + からには + 意志・義務",
        "行くからには、最後まで頑張ります。",
        "既然要去，就堅持到底。",
        "N2",
    ),
    "〜に違いない": (
        "一定…；肯定…",
        "V / いAdj / なAdj + に違いない",
        "彼は犯人に違いない。",
        "他一定是犯人。",
        "N3",
    ),
    "〜に決まっている": (
        "肯定…；一定…（說話者確信）",
        "V / いAdj + に決まっている",
        "彼は犯人に決まっている。",
        "他肯定是犯人。",
        "N2",
    ),
    "〜はずがない": (
        "不可能…；不會…",
        "V / いAdj + はずがない",
        "彼がそんなことをするはずがない。",
        "他不可能做那種事。",
        "N3",
    ),
    "〜わけではない": (
        "並非…；不完全是…",
        "V / いAdj + わけではない",
        "行きたくないわけではない。",
        "並非不想去。",
        "N3",
    ),
    "〜わけだ": (
        "難怪…；原來…",
        "V / いAdj + わけだ",
        "暖かいわけだ。春になったからだ。",
        "難怪暖和，因為春天到了。",
        "N3",
    ),
    "〜ばかりでなく〜も": (
        "不僅…而且…",
        "A ばかりでなく B も",
        "彼は英語ばかりでなく、中国語も話せます。",
        "他不僅會英語，也會中文。",
        "N3",
    ),
    "〜たとたん": (
        "一…就…（意外結果）",
        "Vた + とたん（に）",
        "ドアを開けたとたん、猫が飛び出した。",
        "一開門，貓就跳了出來。",
        "N2",
    ),
    "〜ように": (
        "為了…；以便…",
        "V辞書形 / ない形 + ように",
        "忘れないように、メモします。",
        "為了不忘記，我會做筆記。",
        "N4",
    ),
    "〜てしまう": (
        "做完…；不小心…",
        "Vて + しまう",
        "宿題を忘れてしまいました。",
        "不小心忘了作業。",
        "N4",
    ),
    "〜ことがある": (
        "有時會…；曾經…",
        "Vた + ことがある",
        "日本へ行ったことがあります。",
        "曾經去過日本。",
        "N4",
    ),
    "〜たり〜たり": (
        "又…又…；列舉動作",
        "Vた + り、Vた + りする",
        "週末は買い物をしたり、映画を見たりします。",
        "週末又逛街又看電影。",
        "N4",
    ),
    "〜なければなりません": (
        "必須…",
        "Vない + ければなりません",
        "約束を守らなければなりません。",
        "必須遵守約定。",
        "N4",
    ),
    "〜なくてもいい": (
        "不必…；不…也可以",
        "Vない + くてもいい",
        "靴を脱がなくてもいいです。",
        "不脱鞋也可以。",
        "N4",
    ),
    "〜ないでください": (
        "請不要…",
        "Vない + でください",
        "ここでタバコを吸わないでください。",
        "請不要在這裡吸煙。",
        "N4",
    ),
    "〜てあります": (
        "已經…好了（狀態留存）",
        "Vて + あります",
        "もうチケットは買ってあります。",
        "票已經買好了。",
        "N3",
    ),
    "〜ておきます": (
        "事先…好",
        "Vて + おきます",
        "会議の資料を準備しておきます。",
        "事先準備好會議資料。",
        "N3",
    ),
}


def normalize_pattern(point: str) -> str:
    point = point.strip()
    if not point.startswith("〜") and not point.startswith("~"):
        if re_match := __import__("re").search(r"[〜~][^、，/\s]+", point):
            return re_match.group(0)
    return point.split("/")[0].split("、")[0].strip()


def lookup_grammar(pattern: str) -> tuple[str, str, str, str, str] | None:
    key = normalize_pattern(pattern)
    if key in GRAMMAR_KB:
        return GRAMMAR_KB[key]
    # Longer keys first to avoid partial false positives (e.g. として vs は別として)
    for kb_key in sorted(GRAMMAR_KB, key=len, reverse=True):
        if key == kb_key or key.startswith(kb_key):
            return GRAMMAR_KB[kb_key]
    return None
