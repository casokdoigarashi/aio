# -*- coding: utf-8 -*-
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

TEAL="FF1B5F5B"; PALE="FFDCEEEA"; GREY="FFF2F5F5"; AMBER="FFFDF3E2"; RUST="FFFBEDE8"
thin=Side(style="thin", color="FFCFDCDA")
bd=Border(left=thin,right=thin,top=thin,bottom=thin)
F="ヒラギノ角ゴ ProN W3"

wb=Workbook(); ws=wb.active; ws.title="見積内訳_改定案"

def st(c, bold=False, size=10, bg=None, color="FF22323A", wrap=False, ha="left", va="center"):
    c.font=Font(name=F, bold=bold, size=size, color=color)
    if bg: c.fill=PatternFill("solid", fgColor=bg)
    c.alignment=Alignment(horizontal=ha, vertical=va, wrap_text=wrap)
    c.border=bd

r=1
ws.cell(r,1,"御見積 内訳（改定案）　クラウドファンディング実施一式"); st(ws.cell(r,1),bold=True,size=14); r+=1
ws.cell(r,1,"lipro_見積_0730 をベースに、金額未記入項目の充当・広告予算の分離・追加推奨項目を反映した内訳案"); st(ws.cell(r,1),size=9,color="FF5D717B"); r+=1
ws.cell(r,1,"作成 2026/7/30　株式会社Casokdo　／　想定公開 2026年11月11日・終了 12月25日（45日間）　／　媒体 きびだんご × GREEN FUNDING 併催"); st(ws.cell(r,1),size=9,color="FF5D717B"); r+=2

hdr=["ブロック","セクション","項目名","前提・仕様の明記例","数量","単位","単価(下限)","単価(上限)","金額(下限)","金額(上限)","区分","担当","状態"]
for i,h in enumerate(hdr,1):
    st(ws.cell(r,i,h), bold=True, size=9.5, bg=TEAL, color="FFFFFFFF", wrap=True, ha="center")
ws.row_dimensions[r].height=32
HDR=r; r+=1

# (block, section, name, spec, qty, unit, lo, hi, kind, owner, state)
ROWS=[
 ("A","手続き・契約・基本設計","プラットフォーム担当者とのMTG、プロジェクト基本情報整理","2媒体（きびだんご／GREEN FUNDING）分の窓口対応を含む",1,"式",50000,80000,"フィー","Casokdo","既存/要増額検討"),
 ("A","企画・戦略","競合クラファン調査・着地シミュレーション","同カテゴリ類似案件の着地額・価格帯・支援者数の分析",1,"式",50000,80000,"フィー","Casokdo","★追加推奨"),
 ("A","企画・戦略","目標金額・価格設計（逆算）","原価・手数料20%・送料・関税から支援価格を逆算",1,"式",50000,50000,"フィー","Casokdo","★追加推奨"),
 ("A","企画・戦略","KPI設計・広告シミュレーション","目標支援者数／許容CPA／週次判断基準の設定",1,"式",50000,50000,"フィー","Casokdo","★追加推奨"),
 ("A","商品・コンテンツ設計","商品ストーリー整理","訴求軸・比較軸の整理",1,"式",15000,15000,"フィー","Casokdo","既存"),
 ("A","商品・コンテンツ設計","リターン設計（支援プラン）","早割／数量限定／セット組み／中盤投入枠の設計",1,"式",15000,50000,"フィー","Casokdo","既存/要増額検討"),
 ("A","法務・規制対応","認証状況の棚卸し・確認整理","技適（電波法）／PSE（電気用品安全法）の取得状況・表示方法",1,"式",50000,50000,"フィー","Casokdo＋CL","★追加推奨（最優先）"),
 ("A","法務・規制対応","ページ表現の法規チェック","景品表示法（優良誤認・No.1表記）／薬機法／特商法表記",1,"式",50000,50000,"フィー","Casokdo","★追加推奨"),
 ("A","撮影・素材制作","写真撮影　物撮り","白背景＋質感カット 計10カット／レタッチ込",1,"式",100000,150000,"フィー","Casokdo","▲金額未記入→充当"),
 ("A","撮影・素材制作","写真撮影　シーン撮影","使用シーン10カット／モデル1名（モデル費は実費別）",1,"式",120000,180000,"フィー","Casokdo","▲金額未記入→充当"),
 ("A","撮影・素材制作","動画撮影　メイン動画（1〜2分）","1日／構成台本・ナレーション別",1,"式",250000,400000,"フィー","Casokdo","▲金額未記入→充当"),
 ("A","撮影・素材制作","スタジオ費　8時間想定","機材・照明込",1,"式",80000,150000,"フィー","Casokdo","▲金額未記入→充当"),
 ("A","撮影・素材制作","SNS・広告用短尺（15〜30秒）","3本／縦横比3種書き出し",1,"式",120000,200000,"フィー","Casokdo","▲金額未記入→充当"),
 ("A","撮影・素材制作","動画編集費","メイン1本＋短尺3本／字幕・BGM込／修正2回",1,"式",200000,300000,"フィー","Casokdo","▲金額未記入→充当"),
 ("A","撮影・素材制作","図解・インフォグラフィック制作費","3枚（AI活用制作）",1,"式",45000,90000,"フィー","Casokdo","▲金額未記入→充当"),
 ("A","ページ制作","クラウドファンディングページ構成設計費","訴求順・比較・スペック表・FAQの設計",1,"式",30000,30000,"フィー","Casokdo","既存"),
 ("A","ページ制作","ページ原稿制作費","5,000文字程度想定",1,"式",100000,100000,"フィー","Casokdo","既存"),
 ("A","ページ制作","ページ制作費（きびだんご）","1媒体目",1,"式",100000,100000,"フィー","Casokdo","既存"),
 ("A","ページ制作","ページ制作費（GREEN FUNDING）","2媒体目・原稿流用／フォーマット組み直し",1,"式",150000,150000,"フィー","Casokdo","★追加推奨（併催時必須）"),
 ("A","ページ制作","修正対応、公開設定費","修正3回想定（きびだんご分）",1,"式",30000,30000,"フィー","Casokdo","既存"),
 ("A","ページ制作","媒体審査対応・修正（2媒体分）","審査3〜7営業日／差し戻し対応",1,"式",50000,50000,"フィー","Casokdo","★追加推奨"),
 ("A","計測・デジタル基盤","計測環境構築","GA4／Meta Pixel／UTM設計（LP側で計測設計）",1,"式",80000,80000,"フィー","Casokdo","★追加推奨"),
 ("A","計測・デジタル基盤","広告クリエイティブ制作","バナー・動画 初期5〜8本＋期間中の差し替え",1,"式",200000,200000,"フィー","Casokdo","★追加推奨"),
 ("A","計測・デジタル基盤","LINE公式アカウント開設・運用","自社側の事前登録リスト運用（GF公式LINE配信とは別）",1,"式",80000,80000,"フィー","Casokdo","★追加推奨"),
 ("A","広告・運用（制作）","ティザーページ企画費","LP想定、Instagramへ誘導",1,"式",30000,30000,"フィー","Casokdo","既存"),
 ("A","広告・運用（制作）","ティザーページデザイン費","LP想定",1,"式",120000,120000,"フィー","Casokdo","既存"),
 ("A","広告・運用（制作）","ティザーページコーディング費","LP想定",1,"式",150000,150000,"フィー","Casokdo","既存"),
 ("A","広告・運用（制作）","広告運用費","広告予算 3,000,000円 × 25%（実績額に対して請求）",1,"式",750000,750000,"フィー","Casokdo","既存/算式を明記"),
 ("A","ポップアップ活動費","企画・出店サポート費","蔦屋家電＋出展の企画・申込・提出物対応",1,"式",100000,100000,"フィー","Casokdo","既存"),
 ("A","ポップアップ活動費","出店費（基本什器想定）","蔦屋家電＋ 大型区画 30日（AIカメラ解析・接客ログ・製品ページ作成込）",1,"式",270000,330000,"実費","会場","既存/プラン確定要"),
 ("A","ポップアップ活動費","設営・撤去費","",1,"式",150000,150000,"フィー","Casokdo","既存"),
 ("A","ポップアップ活動費","運営・オペレーション費","内容確定後に別途お見積",1,"式",None,None,"フィー","Casokdo","※0円表記→別途見積へ"),
 ("A","ポップアップ活動費","会場デコレーション手配","各アイテム展示 未定。内容確定後に別途お見積",1,"式",None,None,"フィー","Casokdo","※0円表記→別途見積へ"),
 ("A","事前体験会","事前体験会　開催企画費","メディア・インフルエンサー向け",1,"式",150000,150000,"フィー","Casokdo","既存"),
 ("A","事前体験会","事前体験会　会場費","1日想定",1,"式",100000,100000,"実費","会場","既存"),
 ("A","事前体験会","体験会　運営費","集客、告知、運営（人数×日数の内訳を別紙で明記）",1,"式",450000,450000,"フィー","Casokdo","既存/内訳明記"),
 ("A","PR","プレスリリース制作","公開日朝配信用／ガジェット系メディア想定",1,"式",100000,100000,"フィー","Casokdo","★追加推奨"),
 ("A","PR","メディアリスト作成・アタック","体験会への招集と個別フォロー",1,"式",150000,150000,"フィー","Casokdo","★追加推奨"),
 ("A","期間中の運営","活動報告（新着情報）制作・投稿","週1〜2本×45日＝8〜10本／2媒体投稿",1,"式",120000,160000,"フィー","Casokdo","★追加推奨"),
 ("A","期間中の運営","コメント・問い合わせ一次対応","2媒体＋LP経由／仕様・互換性・技適の技術質問対応",1,"式",200000,200000,"フィー","Casokdo","★追加推奨"),
 ("A","期間中の運営","追加リターン・価格改定の途中投入対応","中盤テコ入れ用",1,"式",50000,50000,"フィー","Casokdo","★追加推奨"),
 ("A","期間中の運営","SNS（Instagram）投稿制作・運用","3ヶ月／週2投稿想定",1,"式",240000,360000,"フィー","Casokdo","★追加推奨"),
 ("A","期間中の運営","週次レポート・広告効果検証","CPA・流入元・リターン別の可視化と配分組み替え",1,"式",100000,100000,"フィー","Casokdo","★追加推奨"),
 ("A","終了後・物流","支援者リスト整備・住所不備対応","2媒体分のマージ・名寄せ・配送データ整形",1,"式",80000,80000,"フィー","Casokdo","★追加推奨"),
 ("A","終了後・物流","同梱物制作","取扱説明書・保証書・サンクスカード",1,"式",150000,250000,"フィー","Casokdo","★追加推奨"),
 ("A","終了後・物流","発送代行手配・梱包設計","倉庫選定・梱包資材設計・出荷指示（配送費・資材費は実費別）",1,"式",100000,100000,"フィー","Casokdo","★追加推奨"),
 ("A","終了後・物流","遅延・不良・返品対応フロー設計","告知文テンプレ／交換対応の窓口設計",1,"式",50000,50000,"フィー","Casokdo","★追加推奨"),
 ("B","広告予算枠","事前広告費","Instagram・Google想定／実費精算・上限管理",1,"式",1000000,1000000,"実費枠","媒体","既存/【B】へ分離"),
 ("B","広告予算枠","開催中広告費","Instagram・Google想定／実費精算・上限管理",1,"式",2000000,2000000,"実費枠","媒体","既存/【B】へ分離"),
 ("C","実費","プレスリリース配信費","PR TIMES等 約30,000円/回 × 3回（公開時・中間・達成時）",3,"回",30000,30000,"実費","媒体","★追加推奨"),
 ("C","実費","GREEN FUNDING オプション","GREENティザー ¥82,500〜／New Gadgetレビュー ¥165,000／バイラル動画3本 ¥110,000／LINE配信 ¥55,000（税込・支援金相殺可）",1,"式",250000,450000,"実費","媒体","★追加推奨"),
 ("C","実費","ティザーLP周辺費","ドメイン・サーバー・事前登録フォームツール（3ヶ月）",1,"式",30000,30000,"実費","—","★追加推奨"),
 ("C","実費","モデル・出演者費","発生時",1,"式",None,None,"実費","—","既存（脚注）"),
 ("C","実費","交通費・配送費","","","実費",None,None,"実費","—","既存（脚注）"),
 ("C","実費","知財出願・PL保険・輸入関税","意匠・特許の出願（公開前）／生産物賠償保険／輸入通関","","実費",None,None,"実費","クライアント","★追加推奨"),
 ("D","支援額連動","プラットフォーム手数料","支援総額（送料・消費税込）の20%＋消費税／きびだんご×GF併催時／支援金から相殺","","支援額連動",None,None,"手数料","媒体","率を明記（重要）"),
]

start=r
for row in ROWS:
    blk,sec,name,spec,qty,unit,lo,hi,kind,owner,state=row
    bg = None
    if blk=="B": bg=PALE
    elif blk in ("C","D"): bg=GREY
    if "▲" in state: bg=RUST
    elif "★" in state and blk=="A": bg=AMBER
    st(ws.cell(r,1,blk), bold=True, bg=bg, ha="center")
    st(ws.cell(r,2,sec), bg=bg, wrap=True)
    st(ws.cell(r,3,name), bg=bg, wrap=True)
    st(ws.cell(r,4,spec), size=9, color="FF5D717B", bg=bg, wrap=True)
    st(ws.cell(r,5,qty), bg=bg, ha="center")
    st(ws.cell(r,6,unit), bg=bg, ha="center")
    for col,v in ((7,lo),(8,hi)):
        c=ws.cell(r,col, v if v is not None else "別途")
        st(c, bg=bg, ha="right")
        if v is not None: c.number_format='#,##0'
    for col,src in ((9,7),(10,8)):
        if lo is None or not isinstance(qty,int):
            c=ws.cell(r,col,"別途")
        else:
            c=ws.cell(r,col,f"=IF(ISNUMBER({get_column_letter(src)}{r}),E{r}*{get_column_letter(src)}{r},\"別途\")")
            c.number_format='#,##0'
        st(c, bg=bg, ha="right")
    st(ws.cell(r,11,kind), bg=bg, ha="center", size=9)
    st(ws.cell(r,12,owner), bg=bg, ha="center", size=9)
    st(ws.cell(r,13,state), bg=bg, size=9, wrap=True,
       color=("FFA83E26" if "▲" in state or "重要" in state or "最優先" in state else ("FFB9760B" if "★" in state or "※" in state else "FF5D717B")))
    ws.row_dimensions[r].height=30
    r+=1
end=r-1

r+=1
def total(label, cond, bg):
    global r
    st(ws.cell(r,3,label), bold=True, bg=bg)
    for col in (9,10):
        L=get_column_letter(col)
        c=ws.cell(r,col,f'=SUMIF($A${start}:$A${end},"{cond}",{L}${start}:{L}${end})' if cond!="*" else f'=SUM({L}${start}:{L}${end})')
        c.number_format='#,##0'; st(c, bold=True, bg=bg, ha="right")
    for col in (1,2,4,5,6,7,8,11,12,13): st(ws.cell(r,col), bg=bg)
    ws.row_dimensions[r].height=22
    r+=1

total("【A】制作・運営フィー　小計（税抜）","A",PALE)
total("【B】広告予算枠　小計（税抜・実費精算）","B",PALE)
total("【C】実費　小計（税抜）","C",PALE)
st(ws.cell(r,3,"A＋B＋C 合計（税抜）"), bold=True, size=11, bg=TEAL, color="FFFFFFFF")
for col in (9,10):
    L=get_column_letter(col)
    c=ws.cell(r,col,f"=SUM({L}{r-3}:{L}{r-1})"); c.number_format='#,##0'
    st(c, bold=True, size=11, bg=TEAL, color="FFFFFFFF", ha="right")
for col in (1,2,4,5,6,7,8,11,12,13): st(ws.cell(r,col), bg=TEAL)
TOT=r; r+=1
st(ws.cell(r,3,"消費税（10%）"), bold=True, bg=GREY)
for col in (9,10):
    L=get_column_letter(col); c=ws.cell(r,col,f"={L}{TOT}*0.1"); c.number_format='#,##0'
    st(c, bold=True, bg=GREY, ha="right")
for col in (1,2,4,5,6,7,8,11,12,13): st(ws.cell(r,col), bg=GREY)
r+=1
st(ws.cell(r,3,"税込金額"), bold=True, size=11, bg=PALE)
for col in (9,10):
    L=get_column_letter(col); c=ws.cell(r,col,f"={L}{TOT}*1.1"); c.number_format='#,##0'
    st(c, bold=True, size=11, bg=PALE, ha="right")
for col in (1,2,4,5,6,7,8,11,12,13): st(ws.cell(r,col), bg=PALE)
r+=1
st(ws.cell(r,3,"【D】プラットフォーム手数料"), bold=True, bg=GREY)
st(ws.cell(r,4,"支援総額（送料・消費税込）の20%＋消費税。支援金から相殺のため本合計には含まない"), size=9, color="FF5D717B", bg=GREY, wrap=True)
for col in (1,2,5,6,7,8,9,10,11,12,13): st(ws.cell(r,col), bg=GREY)
r+=3

notes=[
 "■ 表記・条件に追記すべき事項",
 "・納期：2026年11月11日プロジェクト公開（別途スケジュール参照）　※本見積は2026年8月10日までのご発注を前提とした日程です",
 "・本見積有効期限：発行日より30日",
 "・【B】広告予算枠は実費精算・上限管理とし、上限超過時は書面承認を得たうえで追加する。広告運用費（25%）は実際の出稿額に対して請求する。",
 "・発注後のキャンセル：媒体・会場の規定に準じ、既発生分＋所定のキャンセル料を実費請求（蔦屋家電＋は申込以降のキャンセルで所定料金が発生）。",
 "・広告費・出展費の立替：可／立替手数料 5%（要協議）。GREEN FUNDINGは支援金相殺での支払いに対応。",
 "・プラットフォーム手数料は送料・税金を含む支援総額に対して適用され、その金額に消費税が加算されます。",
 "",
 "■ 状態欄の凡例",
 "▲金額未記入→充当　：元見積で数量・単価が空欄だった行。参考レンジを充当（要・相見積による確定）",
 "★追加推奨　：元見積に無く、追加を推奨する項目",
 "※0円表記→別途見積へ　：元見積で0円と記載されていた行。無償提供と誤読されるため表記変更を推奨",
 "",
 "■ 損益分岐の目安（施策費 9,000,000円・手数料20%・原価率別）",
 "原価率20% → 支援総額 15,000,000円 ／ 原価率30% → 18,000,000円 ／ 原価率40% → 22,500,000円",
 "※単価は相場ベースの参考値です。撮影・スタジオ・出展プラン等は相見積を取得のうえ確定してください。",
]
for n in notes:
    c=ws.cell(r,1,n)
    c.font=Font(name=F, size=9.5, bold=n.startswith("■"), color=("FF1B5F5B" if n.startswith("■") else "FF5D717B"))
    c.alignment=Alignment(vertical="center")
    r+=1

for col,w in ((1,7),(2,20),(3,34),(4,52),(5,6),(6,7),(7,12),(8,12),(9,13),(10,13),(11,9),(12,12),(13,22)):
    ws.column_dimensions[get_column_letter(col)].width=w
ws.freeze_panes=f"A{HDR+1}"
ws.sheet_view.showGridLines=False
ws.auto_filter.ref=f"A{HDR}:M{end}"

out="docs/crowdfunding/見積内訳_改定案_20260730.xlsx"
wb.save(out); print("saved", out)
