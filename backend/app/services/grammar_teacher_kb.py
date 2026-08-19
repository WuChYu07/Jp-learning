"""Professional teacher knowledge — meaning, examples, and OK/NG usage guides."""

from __future__ import annotations

from dataclasses import dataclass

from curriculum.grammar_kb import normalize_pattern


@dataclass(frozen=True)
class TeacherGrammarEntry:
    meaning_zh: str
    connection_rule: str
    example_jp: str
    example_zh: str
    usage_when: str
    usage_avoid: str
    common_mistakes: str
    jlpt: str


# pattern_key (normalized) -> teacher entry
TEACHER_GRAMMAR: dict[str, TeacherGrammarEntry] = {
    "のは": TeacherGrammarEntry(
        meaning_zh="針對某行為發表評價、判斷或感想",
        connection_rule="[動詞辞書形]の + は + [評價/感想]",
        example_jp="早起きするのは、健康にいいです。",
        example_zh="早起這件事對健康很好。",
        usage_when="想對「做某件事」表達個人看法、評價時 | 後面接 いい、悪い、難しい、楽しい 等",
        usage_avoid="後面接具體動作受詞（看、聽、忘記）→ 應改用 のを",
        common_mistakes="與 のが（能力/喜好）、のを（動作受詞）混淆",
        jlpt="N4",
    ),
    "のが": TeacherGrammarEntry(
        meaning_zh="表達對某動作的能力、喜好或特質",
        connection_rule="[動詞辞書形]の + が + [好き、上手、下手、得意、苦手]",
        example_jp="私は音楽を聴くのが好きです。",
        example_zh="我喜歡聽音樂這件事。",
        usage_when="表達喜好、擅長與否、害怕等情感/能力時",
        usage_avoid="表達「對整件事的評價」→ 用 のは",
        common_mistakes="能力・情感對象習慣用が，不要改成は",
        jlpt="N4",
    ),
    "のを": TeacherGrammarEntry(
        meaning_zh="把某動作當作受詞，後接看、聽、忘記、停止等",
        connection_rule="[動詞辞書形]の + を + [見る、聞く、忘れる、やめる]",
        example_jp="鍵を閉めるのを忘れました。",
        example_zh="我忘記鎖門這件事了。",
        usage_when="忘記/看見/聽見/停止「某個行為本身」時",
        usage_avoid="只表達評價或喜好時不要用のを",
        common_mistakes="與 のは、のが 搞混；最常考忘れる、見る、やめる",
        jlpt="N4",
    ),
    "ないでください": TeacherGrammarEntry(
        meaning_zh="請不要…（禮貌禁止）",
        connection_rule="Vない + でください",
        example_jp="ここでタバコを吸わないでください。",
        example_zh="請不要在這裡吸煙。",
        usage_when="禮貌地要求對方不要做某事",
        usage_avoid="對自己用 → ないでください 不自然；正式禁止用 てはいけません",
        common_mistakes="與 なくてもいい（不必）搞反",
        jlpt="N4",
    ),
    "なければなりません": TeacherGrammarEntry(
        meaning_zh="必須…（義務）",
        connection_rule="Vない + ければなりません / なければいけません",
        example_jp="約束を守らなければなりません。",
        example_zh="必須遵守約定。",
        usage_when="表達無論意願如何都必須做的事",
        usage_avoid="表達「不必」→ 用 なくてもいい",
        common_mistakes="口語可說 なきゃ、ならない；不要與 なくてもいい 混淆",
        jlpt="N4",
    ),
    "なくてもいい": TeacherGrammarEntry(
        meaning_zh="不必…；不…也可以",
        connection_rule="Vない + くてもいい",
        example_jp="靴を脱がなくてもいいです。",
        example_zh="不脱鞋也可以。",
        usage_when="表示沒有必要做某事，許可對方不做",
        usage_avoid="表達「必須」→ 用 なければなりません",
        common_mistakes="與 ないでください（請不要）意思完全不同",
        jlpt="N4",
    ),
    "てから": TeacherGrammarEntry(
        meaning_zh="做完前者之後，再做後者（動作順序）",
        connection_rule="Vて + から、V",
        example_jp="ご飯を食べてから、出かけます。",
        example_zh="吃完飯之後出門。",
        usage_when="強調兩個動作的先後順序，前一個先完成",
        usage_avoid="❌ 八時に起きてから、出かけます（明確鐘點時間用 て）| 不能用於單純時間點羅列",
        common_mistakes="與 て（單純連接）混淆；鐘點+て 即可，不需 てから",
        jlpt="N4",
    ),
    "てあります": TeacherGrammarEntry(
        meaning_zh="已經…好了（結果狀態留存）",
        connection_rule="Vて + あります",
        example_jp="もうチケットは買ってあります。",
        example_zh="票已經買好了。",
        usage_when="✅ 某事已做完，狀態現在仍存在 | ✅ 回家發現東西已準備好",
        usage_avoid="❌ 表達「事先為未來準備」→ 用 ておきます",
        common_mistakes="與 ておきます 時間感不同：あります=已完成，おきます=先做好",
        jlpt="N3",
    ),
    "ておきます": TeacherGrammarEntry(
        meaning_zh="事先…好（為未來做準備）",
        connection_rule="Vて + おきます",
        example_jp="明日雨が降りそうだから、傘を買っておきます。",
        example_zh="明天可能下雨，我先去買傘。",
        usage_when="✅ 現在決定先做好，方便之後使用 | ✅ 臨時想到先準備",
        usage_avoid="❌ 說明「已經做好且狀態還在」→ 用 てあります",
        common_mistakes="てあります VS ておきます 是 N3 常考對比",
        jlpt="N3",
    ),
    "〜てくる": TeacherGrammarEntry(
        meaning_zh="變化從過去一路發展到現在；或朝說話者靠近",
        connection_rule="Vて + くる",
        example_jp="寒くなってきましたね。",
        example_zh="天氣漸漸變冷了呢。",
        usage_when="✅ 漸變到現在：慣れてきた、上手になってきた | ✅ 雨が降ってきた（開始下起來）",
        usage_avoid="❌ 單純「來了」的移動義在此不是重點",
        common_mistakes="なりました（結果）vs なってきました（一路變化過程）",
        jlpt="N4",
    ),
    "〜たり〜たり": TeacherGrammarEntry(
        meaning_zh="列舉幾個代表性動作（不等於全部）",
        connection_rule="Vた + り、Vた + り + する",
        example_jp="週末は買い物をしたり、映画を見たりします。",
        example_zh="週末又逛街又看電影之類的。",
        usage_when="✅ 舉例說明習慣、放假常做的事 | ✅ 有「有時…有時…」語感",
        usage_avoid="❌ 只有兩個動作且強調順序/因果 → 用 て形連接 | 【違い】〜て〜て（ONLY 2）",
        common_mistakes="たり只是列舉例子，不是全部活動；常接 します",
        jlpt="N4",
    ),
    "ましょうか": TeacherGrammarEntry(
        meaning_zh="要不要我…？（提出幫忙）",
        connection_rule="Vます形 + ましょうか",
        example_jp="荷物を持ちましょうか。",
        example_zh="要不要我幫您拿行李？",
        usage_when="主動提議為對方做某事",
        usage_avoid="邀請對方一起做 → 用 ましょう",
        common_mistakes="與 ましょう（一起…吧）語感不同",
        jlpt="N4",
    ),
    "ています": TeacherGrammarEntry(
        meaning_zh="動作進行中 / 結果狀態持續 / 習慣",
        connection_rule="Vて + います",
        example_jp="今、雨が降っています。",
        example_zh="現在正在下雨。",
        usage_when="✅ 進行中 | ✅ 結婚しています、知っています（狀態）| ✅ 職業・習慣",
        usage_avoid="短暫瞬間動作較少用",
        common_mistakes="接近英文進行式，但日語更常表狀態持續",
        jlpt="N4",
    ),
    "てもいいですか": TeacherGrammarEntry(
        meaning_zh="可以…嗎？（徵求許可）",
        connection_rule="Vて + もいいですか",
        example_jp="窓を閉めてもいいですか。",
        example_zh="可以關窗嗎？",
        usage_when="禮貌徵求許可",
        usage_avoid="禁止 → てはいけません；不必 → なくてもいい",
        common_mistakes="與 てはいけません 成對學習",
        jlpt="N4",
    ),
    "〜は別として": TeacherGrammarEntry(
        meaning_zh="…姑且不論；先不談…",
        connection_rule="N + は別として",
        example_jp="値段は別として、品質はいいです。",
        example_zh="價格姑且不論，品質很好。",
        usage_when="暫時擱置某議題，討論其他方面",
        usage_avoid="❌ 不是「作為…」的意思 → 那是 として",
        common_mistakes="不要與 として（作為）混淆",
        jlpt="N2",
    ),
    "〜てからでなけらば": TeacherGrammarEntry(
        meaning_zh="不…就不能…（必須先…）",
        connection_rule="Vて + からでなければ",
        example_jp="許可をもらってからでなければ行けません。",
        example_zh="不取得許可就不能去。",
        usage_when="強調必須先完成前一動作，才能做後者",
        usage_avoid="單純時間順序 → 用 てから 即可",
        common_mistakes="でなけらば 為口語/筆記縮寫，正式寫法為 でなければ",
        jlpt="N2",
    ),
    "〜てからでないと": TeacherGrammarEntry(
        meaning_zh="不…就不能…（必須先…）",
        connection_rule="Vて + からでないと / からでなければ",
        example_jp="予約してからでないと入れません。",
        example_zh="不預約就不能進去。",
        usage_when="強調必須先完成前一動作，才能做後者",
        usage_avoid="單純時間順序 → 用 てから 即可",
        common_mistakes="與 てから（單純先後）語感不同，更強調必要條件",
        jlpt="N2",
    ),
    "〜と": TeacherGrammarEntry(
        meaning_zh="自然結果；條件（最嚴格）",
        connection_rule="V辞書形 + と",
        example_jp="ここを押すと、ドアが開きます。",
        example_zh="按這裡，門就會開。",
        usage_when="✅ 必然發生的結果、科學真理、機械反應",
        usage_avoid="❌ 後半句不能有意志、希望、命令、請求（〜しよう、〜てください 等）",
        common_mistakes="與 たら、ば、なら 限制不同；と 最嚴格",
        jlpt="N4",
    ),
    "可能形": TeacherGrammarEntry(
        meaning_zh="能夠…；會…（能力/條件）",
        connection_rule="五段：え段+る；一段：られる；する→できる；来る→来られる",
        example_jp="日本語が話せます。",
        example_zh="會說日語。",
        usage_when="✅ 日常會話優先可能動詞 | ✅ 能力、環境允許",
        usage_avoid="❌ 食べることが食べられる（重複）| ❌ を 要改成 が | ❌ 見える/聞こえる 不是意志可能",
        common_mistakes="可能形 vs ことができる：口語用可能形，書面用ことができる",
        jlpt="N4",
    ),
    "〜に違いない": TeacherGrammarEntry(
        meaning_zh="一定…；肯定…（有根據的推斷）",
        connection_rule="V / いAdj / なAdj + に違いない",
        example_jp="彼は犯人に違いない。",
        example_zh="他一定是犯人。",
        usage_when="有根據地確信（きっと〜だ）",
        usage_avoid="沒有根據的單純猜測 → かもしれない",
        common_mistakes="比 だろう 語氣更肯定",
        jlpt="N3",
    ),
    "〜わけではない": TeacherGrammarEntry(
        meaning_zh="並非…；不完全是…",
        connection_rule="V / いAdj + わけではない",
        example_jp="行きたくないわけではない。",
        example_zh="並非不想去。",
        usage_when="部分否定、澄清誤解",
        usage_avoid="全盤否定用 ない 即可",
        common_mistakes="與 わけがない（不可能）不同",
        jlpt="N3",
    ),
    "〜向き": TeacherGrammarEntry(
        meaning_zh="本質上適合…的（天生適合）",
        connection_rule="N + 向き",
        example_jp="子供向きの本。",
        example_zh="適合小孩的書。",
        usage_when="事物本身特性就適合該對象",
        usage_avoid="刻意針對市場設計 → 用 向け",
        common_mistakes="向き（天然）vs 向け（人為針對）",
        jlpt="N2",
    ),
    "〜向け": TeacherGrammarEntry(
        meaning_zh="為特定對象製作/設計的",
        connection_rule="N + 向け",
        example_jp="初心者向けの教材。",
        example_zh="面向初學者的教材。",
        usage_when="產品、教材等刻意針對某客群",
        usage_avoid="天生適合 → 用 向き",
        common_mistakes="向け強調人為設計；向き強調本質",
        jlpt="N2",
    ),
}


def lookup_teacher(pattern: str) -> TeacherGrammarEntry | None:
    key = normalize_pattern(pattern)
    if key in TEACHER_GRAMMAR:
        return TEACHER_GRAMMAR[key]
    compact = key.replace("~", "〜").replace(" ", "")
    # Longest keys first; require exact or full normalized match only
    for kb_key in sorted(TEACHER_GRAMMAR, key=len, reverse=True):
        kb_compact = kb_key.replace("~", "〜").replace(" ", "")
        if compact == kb_compact:
            return TEACHER_GRAMMAR[kb_key]
    return None
