import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ページ設定
st.set_page_config(page_title="PC Build Simulator", page_icon="icon.png", layout="wide")

# タイトル
st.title("🖥️ PC Build Simulator")
st.markdown("---")

# CSVをロード
@st.cache_data
def load_parts_data():
    return pd.read_csv("parts.csv")

parts_df = load_parts_data()

# パーツタイプごとに分類
part_types = parts_df["type"].unique().tolist()

# 表示ラベルを定義
type_labels = {
    "CPU": "CPU",
    "GPU": "GPU",
    "MEM": "メモリ",
    "SSD": "ストレージ",
    "MB": "マザーボード",
    "PSU": "電源",
    "CASE": "ケース",
    "COOLER": "CPUクーラー",
    "FAN": "ファン"
}

parts_by_type = {}
for tp in part_types:
    cols = ["name", "price", "score"]
    optional_cols = ["power", "socket", "mem_type", "wattage", "power_req"]
    available_cols = [c for c in optional_cols if c in parts_df.columns]
    cols.extend(available_cols)
    parts_by_type[tp] = parts_df[parts_df["type"] == tp][cols].reset_index(drop=True)

# おすすめ自動構成ロジック
def recommend_parts(parts_df, purpose, budget):
    budget_ratios = {
        "ゲーム": {"CPU": 0.18, "GPU": 0.35, "MEM": 0.10, "SSD": 0.12, "MB": 0.08, "PSU": 0.06, "CASE": 0.05, "COOLER": 0.04, "FAN": 0.02},
        "クリエイティブ作業": {"CPU": 0.25, "GPU": 0.20, "MEM": 0.12, "SSD": 0.15, "MB": 0.08, "PSU": 0.07, "CASE": 0.05, "COOLER": 0.05, "FAN": 0.03},
        "動画視聴・ネット": {"CPU": 0.20, "GPU": 0.10, "MEM": 0.12, "SSD": 0.18, "MB": 0.10, "PSU": 0.08, "CASE": 0.10, "COOLER": 0.05, "FAN": 0.07},
        "ライト作業": {"CPU": 0.22, "GPU": 0.10, "MEM": 0.13, "SSD": 0.16, "MB": 0.10, "PSU": 0.08, "CASE": 0.08, "COOLER": 0.05, "FAN": 0.08}
    }
    ratios = budget_ratios.get(purpose, budget_ratios["ライト作業"])
    recommended = {}

    for tp in part_types:
        parts = parts_by_type[tp].copy()
        if parts.empty:
            continue

        target = int(budget * ratios.get(tp, 0.05))
        target = max(target, int(parts["price"].min()))
        affordable = parts[parts["price"] <= target]

        if not affordable.empty:
            chosen = affordable.sort_values(["score", "price"], ascending=[False, True]).iloc[0]
        else:
            chosen = parts.sort_values(["price", "score"], ascending=[True, False]).iloc[0]

        recommended[tp] = chosen["name"]

    return recommended

# 互換性チェック関数
def get_attr(tp, name, attr):
    if name == "選択なし":
        return None
    if tp not in parts_by_type or parts_by_type[tp].empty:
        return None
    row = parts_by_type[tp][parts_by_type[tp]["name"] == name]
    if row.empty:
        return None
    if attr not in row.columns:
        return None
    val = row[attr].values[0]
    return val if not pd.isna(val) else None

def check_compatibility(selected_parts):
    warnings = []
    
    cpu_socket = get_attr("CPU", selected_parts.get("CPU"), "socket")
    mb_socket = get_attr("MB", selected_parts.get("MB"), "socket")
    mb_mem_type = get_attr("MB", selected_parts.get("MB"), "mem_type")
    mem_type = get_attr("MEM", selected_parts.get("MEM"), "mem_type")
    psu_wattage = get_attr("PSU", selected_parts.get("PSU"), "wattage")
    gpu_power = get_attr("GPU", selected_parts.get("GPU"), "power_req")
    cpu_power = get_attr("CPU", selected_parts.get("CPU"), "power")
    
    if cpu_socket and mb_socket and cpu_socket != mb_socket:
        warnings.append("⚠️ CPUとマザーボードのソケットが一致しません。")
    
    if mem_type and mb_mem_type and mem_type != mb_mem_type:
        warnings.append("⚠️ メモリタイプとマザーボードが一致しません。")
    
    if psu_wattage and gpu_power and cpu_power:
        total_power = gpu_power + cpu_power + 100  # 余裕分
        if total_power > psu_wattage:
            warnings.append(f"⚠️ 電源容量が不足しています。必要: {total_power}W, 現在: {psu_wattage}W")
    
    return warnings

# サイドバーでパーツ選択
st.sidebar.header("🔧 パーツを選択")

st.sidebar.subheader("✨ おすすめ構成")
purpose = st.sidebar.radio("ご利用目的", ["ゲーム", "クリエイティブ作業", "ライト作業", "動画視聴・ネット"], index=0)
budget = st.sidebar.slider("予算（円）", 50000, 300000, 150000, step=10000)

if st.sidebar.button("おすすめ構成を生成"):
    recommended_parts = recommend_parts(parts_df, purpose, budget)
    for tp, name in recommended_parts.items():
        st.session_state[f"select_{tp}"] = name
    st.session_state["recommend_message"] = f"{purpose}向けのおすすめ構成を予算{budget:,}円で生成しました。"

if "recommend_message" in st.session_state:
    st.sidebar.info(st.session_state["recommend_message"])

selected_parts = {}
for tp in part_types:
    label = type_labels.get(tp, tp)
    options = ["選択なし"] + parts_by_type[tp]["name"].tolist()
    selected_parts[tp] = st.sidebar.selectbox(label, options, key=f"select_{tp}")

# 選択したパーツの価格を取得する関数
def get_price(part_type, part_name):
    if part_name == "選択なし":
        return 0
    result = parts_by_type[part_type][parts_by_type[part_type]["name"] == part_name]["price"]
    return result.values[0] if len(result) > 0 else 0

# 選択したパーツのスコアを取得する関数
def get_score(part_type, part_name):
    if part_name == "選択なし":
        return 0
    result = parts_by_type[part_type][parts_by_type[part_type]["name"] == part_name]["score"]
    return result.values[0] if len(result) > 0 else 0

# 価格を計算
selected_prices = {tp: get_price(tp, name) for tp, name in selected_parts.items()}
total_price = sum(selected_prices.values())

# メイン画面：構成一覧
st.header("📋 PC構成一覧")

# 構成表を作成
config_data = {
    "パーツ": [],
    "商品名": [],
    "価格": []
}
for tp in part_types:
    part_label = type_labels.get(tp, tp)
    part_name = selected_parts[tp] if selected_parts[tp] != "選択なし" else "-"
    part_price = selected_prices[tp]
    config_data["パーツ"].append(part_label)
    config_data["商品名"].append(part_name)
    config_data["価格"].append(f"¥{part_price:,.0f}" if part_price > 0 else "¥0")

config_data["パーツ"].append("合計")
config_data["商品名"].append("")
config_data["価格"].append(f"¥{total_price:,.0f}")

config_df = pd.DataFrame(config_data)
st.dataframe(config_df, width='stretch', hide_index=True)

# 合計金額を強調表示
st.metric("💰 合計金額", f"¥{total_price:,.0f}")

# コメント生成ロジック
def generate_comment(cpu_score, gpu_score, total, selected_count, total_count):
    comments = []
    
    # GPU性能に基づくコメント
    if gpu_score >= 90:
        comments.append("🎮 ハイエンド・ゲーミング向け！重いゲームも快適に動作します。")
    elif gpu_score >= 75:
        comments.append("🎮 ゲーミング向け。最新ゲームも中程度以上の設定で楽しめます。")
    elif gpu_score >= 60:
        comments.append("🎮 軽～中程度のゲーミング向け。スポーツゲームなどに最適。")
    elif gpu_score > 0:
        comments.append("💻 軽めのゲーム・動画視聴に適しています。")
    
    # CPU性能に基づくコメント
    if cpu_score >= 85:
        comments.append("⚡ 最高スペックのCPU。マルチタスク・クリエイティブ作業に最適。")
    elif cpu_score >= 75:
        comments.append("⚡ 高性能CPU。快適にマルチタスク処理できます。")
    elif cpu_score >= 68:
        comments.append("💪 バランスの取れたCPU。日常利用は十分快適。")
    
    # 価格に基づくコメント
    if total <= 100000:
        comments.append("💡 コスパ重視の構成。予算を抑えたい方向け。")
    elif total <= 200000:
        comments.append("💡 バランス型の構成。一般的なニーズに対応。")
    else:
        comments.append("💎 高級構成。最高のパフォーマンスを求める方向け。")
    
    # 完全性のコメント
    if selected_count == 0:
        comments.append("⚠️ パーツをまず選択してください。")
    elif selected_count == total_count:
        comments.append("✅ すべてのパーツが選択されています。")
    else:
        comments.append(f"⚠️ まだ{total_count - selected_count}個のパーツが未選択です。")

    return "\n".join(comments)

# パーツのスコア取得
cpu_score = get_score("CPU", selected_parts.get("CPU", "選択なし"))
gpu_score = get_score("GPU", selected_parts.get("GPU", "選択なし"))
selected_count = sum(1 for name in selected_parts.values() if name != "選択なし")
total_count = len(selected_parts)

# コメント表示
st.header("💬 構成コメント")
st.info(generate_comment(cpu_score, gpu_score, total_price, selected_count, total_count))

# 互換性チェック
st.header("🔍 互換性チェック")
if st.button("互換性をチェック"):
    warnings = check_compatibility(selected_parts)
    if warnings:
        for w in warnings:
            st.error(w)
    else:
        st.success("✅ 互換性に問題ありません。")

# PDF出力機能
def generate_pdf(config_data, total_price, comment):
    """PDF見積書を生成"""
    buffer = BytesIO()
    
    # SimpleDocTemplateを使用
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                           rightMargin=15*mm, leftMargin=15*mm,
                           topMargin=15*mm, bottomMargin=15*mm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # タイトル
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=12,
        alignment=TA_CENTER
    )
    elements.append(Paragraph("PC 見積書", title_style))
    elements.append(Spacer(1, 10))
    
    # 日付
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_RIGHT
    )
    elements.append(Paragraph(f"発行日: {datetime.now().strftime('%Y年%m月%d日')}", date_style))
    elements.append(Spacer(1, 15))
    
    # 構成表
    table_data = [
        ["パーツ", "商品名", "価格"]
    ]
    for i in range(len(config_data["パーツ"]) - 1):
        table_data.append([
            config_data["パーツ"][i],
            config_data["商品名"][i],
            config_data["価格"][i]
        ])
    table_data.append(["", "合計", f"¥{total_price:,.0f}"])
    
    table = Table(table_data, colWidths=[40*mm, 100*mm, 50*mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e6f2ff')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f9f9f9')])
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 15))
    
    # コメント
    comment_style = ParagraphStyle(
        'CommentStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#555555'),
        spaceAfter=6
    )
    elements.append(Paragraph("<b>構成コメント:</b>", styles['Heading3']))
    for line in comment.split('\n'):
        elements.append(Paragraph(f"• {line}", comment_style))
    
    # PDF生成
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ダウンロードボタン
st.header("📥 ダウンロード")
if total_price > 0:
    comment = generate_comment(cpu_score, gpu_score, total_price, selected_count, total_count)
    pdf_buffer = generate_pdf(config_data, total_price, comment)
    
    st.download_button(
        label="📄 PDF見積書をダウンロード",
        data=pdf_buffer,
        file_name=f"PC見積書_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mime="application/pdf"
    )
else:
    st.warning("⚠️ 最低1つ以上のパーツを選択してください。")

st.markdown("---")
st.markdown("**PC Build Simulator** © 2026 | 初心者向けPC構成シミュレータ")
